"""Bind visual review evidence to the exact generated PDF and its source parts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'scripts'

from .pdf_merger import inspect_pdf, sha256
from .excel_reporter import update_review_report

CHECKS = ('document_identity', 'bibliographic_names', 'english_material_type', 'full_document', 'layout')
BINDINGS = ('publication', 'material_type', 'output_path', 'sha256', 'pages', 'biblio_pages', 'original_pages',
            'biblio_path', 'biblio_sha256', 'original_path', 'original_sha256')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def create_packet(result, path):
    path = Path(path).resolve()
    write_json(path, dict(version=1, **{key:result[key] for key in BINDINGS}, decision='pending',
        reviewer='', review_note='', checks={key:False for key in CHECKS},
        sections={key:dict(present=None, pages=[], note='') for key in ('claims', 'drawings')},
        images=[]))
    return path


def validate_files(packet):
    for field, digest in (('output_path', 'sha256'), ('original_path', 'original_sha256'), ('biblio_path', 'biblio_sha256')):
        path = packet.get(field)
        if field == 'biblio_path' and packet['biblio_pages'] == 0:
            if path is not None or packet.get(digest) is not None:
                raise ValueError('원문 단독의 서지 PDF 정보 불일치')
            continue
        if not path or sha256(path) != packet[digest]:
            raise ValueError('검수 대상 파일 변경 또는 해시 불일치: ' + field)
    counts = (('output_path', 'pages'), ('original_path', 'original_pages'), ('biblio_path', 'biblio_pages'))
    for field, count in counts:
        if packet[count] and len(inspect_pdf(packet[field]).pages) != packet[count]:
            raise ValueError('검수 대상 페이지 수 불일치: ' + field)
    if packet['pages'] != packet['biblio_pages'] + packet['original_pages']:
        raise ValueError('서지·원문 페이지 합계 불일치')


def required_pages(packet, require_sections=False):
    b, total = packet['biblio_pages'], packet['pages']
    pages = set(range(1, b+1)) | {b+1, total}
    for key in ('claims', 'drawings'):
        section = packet['sections'][key]
        if require_sections:
            if type(section.get('present')) is not bool or not str(section.get('note', '')).strip():
                raise ValueError('청구범위/도면 존재 여부와 경계 또는 부재 근거 필요: ' + key)
            if section['present'] and not section.get('pages'):
                raise ValueError('청구범위/도면 경계 페이지 필요: ' + key)
            if not section['present'] and section.get('pages'):
                raise ValueError('없는 구간에 페이지가 지정됨: ' + key)
        for page in section.get('pages', []):
            if type(page) is not int or not b < page <= total:
                raise ValueError('원문 범위 밖 경계 페이지: ' + key)
            pages.add(page)
    return pages


def render_packet(path, pages=()):
    """Render evidence, but never infer that anyone inspected it."""
    import pypdfium2 as pdfium
    path = Path(path).resolve()
    packet = json.loads(path.read_text(encoding='utf-8-sig'))
    validate_files(packet)
    wanted = required_pages(packet) | set(pages)
    if any(type(p) is not int or not 1 <= p <= packet['pages'] for p in wanted):
        raise ValueError('렌더링 페이지 범위 오류')
    folder = path.parent / (path.stem + '-images')
    folder.mkdir(exist_ok=True)
    images = {item['page']:item for item in packet['images']}
    with pdfium.PdfDocument(packet['output_path']) as document:
        for number in sorted(wanted):
            target = folder / f'page-{number:04d}.png'
            page = document[number-1]
            bitmap = page.render(scale=1.7)
            pil = bitmap.to_pil()
            try:
                pil.save(target)
            finally:
                pil.close(); bitmap.close(); page.close()
            images[number] = dict(page=number, path=str(target), sha256=sha256(target), pdf_sha256=packet['sha256'])
    packet['images'] = [images[p] for p in sorted(images)]
    # Re-rendering never retains a prior approval of changed evidence.
    packet['decision'] = 'pending'
    packet['checks'] = dict.fromkeys(CHECKS, False)
    packet['reviewer'] = ''
    packet['review_note'] = ''
    write_json(path, packet)
    return packet


def approve_or_reject(packet):
    validate_files(packet)
    if not str(packet.get('reviewer', '')).strip() or not str(packet.get('review_note', '')).strip():
        raise ValueError('실제 검수자와 검수/반려 근거가 필요합니다.')
    if packet.get('decision') == 'rejected':
        return False
    if packet.get('decision') != 'approved':
        raise ValueError('검수 결정은 approved 또는 rejected여야 합니다.')
    for key in CHECKS:
        if packet['checks'].get(key) is not True:
            raise ValueError('검수 미완료: ' + key)
    wanted = required_pages(packet, require_sections=True)
    images = {item['page']:item for item in packet['images']}
    if not wanted.issubset(images):
        raise ValueError('검수 이미지 누락: ' + ','.join(map(str, sorted(wanted-set(images)))))
    for number, image in images.items():
        if type(number) is not int or not 1 <= number <= packet['pages'] or image.get('pdf_sha256') != packet['sha256']:
            raise ValueError(f'검수 이미지 누락: {number}')
        path = Path(image['path'])
        if path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n' or sha256(path) != image['sha256']:
            raise ValueError(f'검수 이미지 변경 또는 손상: {number}')
    return True


def apply_review(results_path, packet_path):
    results_path, packet_path = Path(results_path).resolve(), Path(packet_path).resolve()
    results = json.loads(results_path.read_text(encoding='utf-8-sig'))
    packet = json.loads(packet_path.read_text(encoding='utf-8-sig'))
    matches = [r for r in results if r.get('output_path') == packet['output_path']]
    if not matches:
        raise ValueError('결과표에 해당 PDF가 없습니다.')
    for record in matches:
        if any(record.get(key) != packet.get(key) for key in BINDINGS):
            raise ValueError('결과표와 검수 자료의 파일·출처 바인딩 불일치')
    approved = approve_or_reject(packet)
    now = datetime.now(timezone.utc).isoformat()
    for record in matches:
        record.update(review_status='검수 완료' if approved else '검수 반려', final_review_complete=approved,
                      complete_reference=approved and record.get('official_materials_complete') is True,
                      status='검수 완료' if approved else '검수 반려',
                      reviewed_at=now, reviewer=packet['reviewer'], review_note=packet['review_note'],
                      review_packet=str(packet_path), review_packet_sha256=sha256(packet_path),
                      review_evidence=packet)
        record['note'] += ' | 최종 검수: ' + record['review_status'] + ' | ' + packet['review_note']
    # Revalidate all earlier approvals before a new reviewed ZIP is made.
    reviewed = {}
    for record in results:
        if record.get('final_review_complete'):
            evidence = record['review_evidence']
            if any(record.get(key) != evidence.get(key) for key in BINDINGS) or not approve_or_reject(evidence):
                raise ValueError('기존 검수 완료 자료의 근거 불일치')
            reviewed[record['output_path']] = record
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base = results_path.parent / ('검수결과_' + stamp)
    output_json, output_xlsx = base.with_suffix('.json'), base.with_suffix('.xlsx')
    update_review_report(results_path.with_suffix('.xlsx'), output_xlsx, results)
    write_json(output_json, results)
    archive = None
    if reviewed:
        archive = results_path.parent / ('검수완료자료_' + stamp + '.zip')
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
            for path, record in reviewed.items():
                # Store each reviewed document and its evidence in separate folders.
                folder = record['publication'] + '-' + record['sha256'][:12]
                z.write(path, folder + '/' + Path(path).name)
                z.writestr(folder + '/검수기록.json', json.dumps(record['review_evidence'], ensure_ascii=False, indent=2))
                for image in record['review_evidence']['images']:
                    z.write(image['path'], folder + '/images/' + Path(image['path']).name)
            z.write(output_json, output_json.name); z.write(output_xlsx, output_xlsx.name)
            z.writestr('검수안내.txt', '검수 완료된 PDF만 포함합니다. 공식/AI/기계번역/원문 단독 자료 유형은 결과표를 확인하세요. 관청 제출 자체는 수행하지 않았습니다.')
    return dict(review_status='검수 완료' if approved else '검수 반려', reviewed_files=len(reviewed),
                input_rows=len(results), approved_rows=sum(r.get('final_review_complete') is True for r in results),
                pending_rows=sum(r.get('review_status') == '검수 대기' for r in results),
                rejected_rows=sum(r.get('review_status') == '검수 반려' for r in results),
                results=str(output_json), report=str(output_xlsx), archive=str(archive) if archive else None)


def main():
    parser = argparse.ArgumentParser(description='병합 후 최종 시각 검수 근거를 결과표에 연결')
    sub = parser.add_subparsers(dest='command', required=True)
    render = sub.add_parser('render'); render.add_argument('--packet', type=Path, required=True)
    render.add_argument('--pages', type=int, nargs='*', default=[])
    apply = sub.add_parser('apply'); apply.add_argument('--packet', type=Path, required=True)
    apply.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'render':
        packet = render_packet(args.packet, args.pages)
        print(json.dumps(dict(images=packet['images'], decision=packet['decision']), ensure_ascii=False))
    else:
        result = apply_review(args.results, args.packet)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['review_status'] == '검수 완료' else 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(2)
