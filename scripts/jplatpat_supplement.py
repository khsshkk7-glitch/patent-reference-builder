"""Explicitly approved JP U machine translation; never a complete reference."""
import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'scripts'

from .input_parser import one
from .browser_session import browser_session, navigate, CollectionError
from .output_paths import output_directory
from .pdf_merger import copy_original_unique, inspect_pdf, sha256

LABEL = 'MACHINE-TRANSLATED SUPPLEMENT — NOT A COMPLETE REFERENCE'
NOTICE = 'This document has been translated by computer.'
READ_SOURCE = """() => {
 const section = name => Array.from(document.querySelectorAll('p0201-areadisp .l-toggle'))
   .find(e => e.querySelector('h3')?.innerText.trim() === name);
 const b = section('Bibliography'), a = section('Overview');
 return {identity:document.querySelector('#p0201_docuTitleArea_lblReferenceNumberTitle')?.innerText || '',
   notice:document.querySelector('#p0201_msgArea_mistranslation')?.innerText || '',
   bibliography:b?.innerText || '', overview:a?.innerText || '',
   images:Array.from(a?.querySelectorAll('img') || []).map(i => ({src:i.src, loaded:i.complete && i.naturalWidth>0}))};
}"""


def validate_source_url(url, patent):
    u = urlparse(url)
    if (patent.country != 'JP' or patent.kind != 'U' or patent.role != 'publication'
        or u.scheme != 'https' or u.netloc != 'www.j-platpat.inpit.go.jp'
        or u.path != f'/c1801/PU/JP-{patent.number}/25/en' or u.query or u.fragment):
        raise ValueError('동일 JP U 공보의 공식 영문 영구 URL(…/25/en)이 필요합니다.')


def validate_snapshot(data, patent):
    if re.sub(r'[^A-Z0-9]', '', data['identity'].upper()) != patent.key:
        raise CollectionError('J-PlatPat 공보번호 또는 종별 불일치')
    if NOTICE not in data['notice'] or 'JPO and INPIT' not in data['notice']:
        raise CollectionError('공식 기계번역 고지 누락')
    b, a = data['bibliography'], data['overview']
    owner_block = b.split('(73)', 1)[-1].split('(72)', 1)[0] if '(73)' in b else ''
    owner = re.search(r'\[Name\]\s*([^\n]+)', owner_block)
    creator = re.search(r'\(72\).*?\[Name\]\s*([^\n]+)', b, re.S)
    if not owner or not creator or '[Problem]' not in a or '[Means for solving]' not in a:
        raise CollectionError('서지 또는 영문 요약 번역이 아직 완료되지 않았습니다.')
    if not all(image['loaded'] for image in data['images']) or not data['images']:
        raise CollectionError('대표도면 로드 미완료')
    if any(urlparse(i['src']).scheme != 'https' or urlparse(i['src']).netloc != 'www.j-platpat.inpit.go.jp' for i in data['images']):
        raise CollectionError('대표도면이 공식 출처가 아닙니다.')
    if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', a + owner[1] + creator[1]):
        raise CollectionError('영문 번역 완료를 확인할 수 없습니다.')


def document_html(data, patent, url):
    def section(text):
        lines = [line for line in text.splitlines() if line.strip() not in ('Close', 'Open')]
        return '<div class="source">' + escape('\n'.join(lines)) + '</div>'
    return '''<!doctype html><meta charset="utf-8"><style>
      @page {size:A4; margin:14mm} body {font:10pt Arial,sans-serif;color:#111}
      h1 {font-size:14pt} .notice {border:1px solid #444;padding:8px;white-space:pre-wrap;font-size:9pt}
      .source {white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.3;margin:12px 0}
      img {display:block;max-width:140mm;max-height:85mm;margin:auto;object-fit:contain}
      .provenance {font-size:8pt;overflow-wrap:anywhere}
      </style>''' + f'<h1>{LABEL}</h1><p>기계번역 보완자료 · 완성 참증 아님 · {escape(patent.key)}</p>' \
        + '<p class="provenance">Official source: ' + escape(url) + '</p>' \
        + '<div class="notice">' + escape(data['notice']) + '</div>' \
        + section(data['bibliography']) + section(data['overview']) \
        + ''.join('<img src="' + escape(i['src'], quote=True) + '">' for i in data['images'])


def run(args):
    if not args.acknowledge_machine_translation:
        raise ValueError('사용자가 기계번역 별도 보완자료를 명시적으로 허용해야 합니다.')
    patent = one(args.text)
    validate_source_url(args.source_url, patent)
    root = output_directory(args.out)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = root / 'work' / ('jplatpat-' + stamp)
    work.mkdir(parents=True, exist_ok=True)
    with browser_session(args) as page:
        navigate(page, args.source_url, attempts=1)
        # A permanent address opens an exact-document results list first.
        with page.expect_popup() as opened:
            page.get_by_role('link', name=f'JP,{patent.number},U', exact=True).click()
        page = opened.value
        page.wait_for_load_state('domcontentloaded')
        # Translation is asynchronous; names may arrive after the overview.
        import time
        deadline = time.monotonic() + args.timeout
        while True:
            data = page.evaluate(READ_SOURCE)
            try:
                validate_snapshot(data, patent)
                break
            except CollectionError:
                if time.monotonic() >= deadline:
                    (work/'failed-source.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    (work/'failed.html').write_text(page.content(), encoding='utf-8')
                    page.screenshot(path=str(work/'failed.png'), full_page=True)
                    raise
                page.wait_for_timeout(500)
        (work/'source.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        printed = page.context.new_page()
        try:
            printed.set_content(document_html(data, patent, args.source_url), wait_until='networkidle')
            printed.wait_for_function('Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)')
            temporary = work/'supplement.pdf'
            printed.pdf(path=str(temporary), format='A4', print_background=True)
        finally:
            printed.close()
    reader = inspect_pdf(temporary)
    text = '\n'.join(p.extract_text() or '' for p in reader.pages)
    if NOTICE not in text or 'NOT A COMPLETE REFERENCE' not in text or '[Means for solving]' not in text:
        raise CollectionError('인쇄 PDF의 기계번역 고지 또는 요약 누락')
    target, counts = copy_original_unique(temporary, root/'기계번역 보완자료'/patent.filename, len(reader.pages))
    result = dict(publication=patent.key, status='보완자료', result_type='machine_translation_supplement',
        complete_reference=False, translation_type='official_site_machine_translation', source='J-PlatPat',
        source_url=args.source_url, output_path=str(target), filename=target.name,
        pages=counts['pages'], sha256=sha256(target), user_approved_machine_translation=True,
        note='공식 사이트 기계번역 고지 보존; 원문과 별도 보관; 완성 참증으로 집계하지 않음')
    report = root / ('보완자료_' + stamp + '.json')
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def parser():
    p = argparse.ArgumentParser(description='명시적으로 허용한 J-PlatPat JP U 기계번역 별도 보완 PDF')
    p.add_argument('--text', required=True)
    p.add_argument('--source-url', required=True)
    p.add_argument('--acknowledge-machine-translation', action='store_true')
    p.add_argument('--out', type=Path)
    p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--headed', action='store_true')
    p.add_argument('--native-chrome', action='store_true')
    p.add_argument('--channel', choices=['chrome', 'msedge'])
    p.add_argument('--profile')
    p.add_argument('--cdp')
    return p


if __name__ == '__main__':
    run(parser().parse_args())
