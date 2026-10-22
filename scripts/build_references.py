"""CLI: python -m scripts.build_references --text 'JP 2006-198019 A' --out output"""
import argparse
from contextlib import nullcontext
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "scripts"

from .input_parser import extract, one
from .excel_reporter import Row, read_table, write_report
from .pdf_merger import merge_unique, copy_original_unique, sha256
from .output_paths import output_directory
from .collector_common import from_manifest
from .browser_session import browser_session, CollectionError, HumanRequired, HumanWaitTimeout, checkpoint
from . import espacenet_collector, kipris_collector
from .original_identity import IdentityReviewRequired, DocumentIdentityMismatch
from .final_review import create_packet


def parser():
    p = argparse.ArgumentParser(description="영문 서지·초록 + 공식 원문 공보 참증 PDF 제작")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="번호 1개 또는 줄바꿈/쉼표 구분 번호 목록")
    src.add_argument("--input", type=Path, help=".xlsx / .xls / .csv")
    p.add_argument("--out", type=Path, help="저장 폴더. 생략 시 사용자 다운로드 폴더")
    p.add_argument("--column")
    p.add_argument("--sheet")
    p.add_argument("--country", help="국가코드 없는 셀에 적용할 명시적 국가")
    p.add_argument("--role", choices=["publication", "application"], default=None,
                   help="명시한 번호 유형. 생략 시 파일은 헤더로 판단하고 채팅/헤더 없음은 공보번호")
    p.add_argument("--source", choices=["auto", "espacenet", "kipris"], default="auto")
    p.add_argument("--manifest", type=Path, help="검토된 로컬 PDF 및 출처 manifest JSON")
    p.add_argument('--ai-manifest', type=Path, help='원문 대조한 AI 번역/요약 또는 사이트 기계번역 보완 manifest')
    p.add_argument("--selectors", type=Path, help="현재 KIPRIS UI 선택자 JSON")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--zip", action="store_true")
    p.add_argument("--original-only", action="store_true", help="Espacenet 공식 원문만 별도 폴더에 저장 (완성 참증 아님)")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--native-chrome", action="store_true", help="설치된 일반 Chrome을 작업용 프로필로 열고 로컬 연결 (KIPRIS 권장)")
    p.add_argument("--no-fallback", action="store_true", help="KIPRIS 원문 실패 시 Espacenet 대체 수집 금지")
    p.add_argument("--interactive", action="store_true")
    p.add_argument('--original-method',choices=['auto','browser','ops'],default='auto',help='Espacenet 원문: 키 설정 시 공식 OPS 우선, 없으면 기존 브라우저')
    p.add_argument("--human-timeout", type=int, default=300)
    p.add_argument("--timeout", type=int, default=40)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--profile", help="전용 Chromium 프로필 폴더")
    p.add_argument("--cdp", help="사용자가 연 로컬 디버깅 브라우저 URL")
    p.add_argument("--channel", choices=["chrome", "msedge"])
    return p


def input_rows(args):
    if args.input:
        return read_table(args.input, args.column, args.sheet, args.country, args.role)
    # Preserve invalid entries as failures instead of silently dropping them.
    import re
    chunks = [s.strip() for s in re.split(r"[,;\n]+", args.text) if s.strip()]
    rows = []
    role = args.role or 'publication'
    for chunk in chunks:
        patents = extract(chunk, role, args.country)
        if len(patents) > 1:
            base = len(rows) + 2
            rows.extend(Row("입력", base + i, p.key, role, role_source='explicit' if args.role else 'default') for i, p in enumerate(patents))
        else:
            rows.append(Row("입력", len(rows) + 2, chunk, role, role_source='explicit' if args.role else 'default'))
    return {"입력": [("특허번호",)] + [(r.value,) for r in rows]}, {"입력": (0, 1)}, rows


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path else {}


def input_accounting(rows, results):
    return dict(input_rows=len(rows), recorded_rows=len(results),
                remaining_rows=len(rows)-len(results), statuses=dict(Counter(r['status'] for r in results)))


def collect(page, patent, work, args):
    collectors = [kipris_collector] if args.source == "kipris" else [espacenet_collector]
    if patent.country == "KR" and args.source != "kipris":
        collectors.append(kipris_collector)
    errors = []
    diagnostics = []
    for module in collectors:
        try:
            return module.collect(page, patent, work, args)
        except Exception as exc:
            if isinstance(exc,(IdentityReviewRequired,DocumentIdentityMismatch)):
                raise  # Never hide a wrong or unidentified original behind another collector.
            if isinstance(exc, kipris_collector.TranslationRequired):
                raise  # Preserve the collected original and exact resume packet.
            # Keep evidence locally; HTML is data and never executed as instructions.
            name = module.__name__.split(".")[-1]
            errors.append(name + ": " + str(exc).split('\n')[0])
            diagnostics.extend(getattr(exc, 'diagnostics', []))
            try:
                (work / (name + '-error.txt')).write_text(str(exc), encoding='utf-8')
                page.screenshot(path=str(work / (name + "-failure.png")), full_page=True)
                (work / (name + '-failure.html')).write_text(page.content(), encoding='utf-8')
            except Exception:
                pass
            if isinstance(exc, HumanWaitTimeout):
                # Keep evidence, but do not restart a timed-out manual wait.
                raise
            if isinstance(exc, HumanRequired) and args.interactive:
                checkpoint(page, args, str(exc))
                # One retry after human action; no unlimited retry or automated CAPTCHA solving.
                try:
                    return module.collect(page, patent, work, args)
                except Exception as retry:
                    errors.append("확인 후 재시도: " + str(retry))
    error = CollectionError(" | ".join(errors))
    error.diagnostics = diagnostics
    raise error


def run(args):
    if args.ai_manifest and (args.original_only or args.manifest):
        raise ValueError('--ai-manifest는 --original-only/--manifest와 함께 사용할 수 없습니다.')
    if args.original_only and (args.source == 'kipris' or args.manifest):
        raise ValueError('--original-only는 Espacenet 온라인 원문 단독 수집용이며 KIPRIS/참증 manifest와 함께 사용할 수 없습니다.')
    if args.native_chrome and (not args.headed or args.cdp or args.profile or args.channel not in (None, 'chrome')):
        raise ValueError('--native-chrome은 --headed와 함께, --cdp/--profile/Edge 없이 사용하세요.')
    if args.no_fallback and args.source != 'kipris':
        raise ValueError('--no-fallback은 --source kipris 직접 수집 검증에 사용하세요.')
    if args.interactive and not (args.headed or args.cdp):
        raise ValueError("--interactive는 --headed 또는 --cdp와 함께 사용하세요.")
    if not 1 <= args.retries <= 5 or args.timeout < 1 or args.human_timeout < 1 or args.delay < 0:
        raise ValueError("retries: 1~5, timeout/human-timeout: 양수, delay: 0 이상")
    args.out = output_directory(args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    sheets, layouts, rows = input_rows(args)
    if not rows:
        raise ValueError('처리할 특허번호가 없습니다.')
    manifest = load_json(args.manifest)
    ai_manifest = load_json(args.ai_manifest)
    args.selectors = load_json(args.selectors)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.out / "work" / stamp
    run_dir.mkdir(parents=True)
    results, cache = [], {}
    parsed = []
    for row in rows:
        if row.exclusion or row.input_error:
            parsed.append((row, None, row.exclusion or row.input_error))
            continue
        try:
            patent = one(row.value, role=row.role, country=args.country)
            parsed.append((row, patent, None))
        except ValueError as exc:
            parsed.append((row, None, str(exc)))
    if args.dry_run:
        plan = [{"sheet": r.sheet, "row": r.index, "input": r.value, "patent": asdict(p) if p else None,
                 "query": p.query if p else None, "filename": p.filename if p else None, "error": None if r.exclusion else e,
                 "status": "제외" if r.exclusion else ("처리 예정" if p else "실패"),
                 "input_role":r.role, "input_role_source":r.role_source,
                 "note": r.exclusion or e or ""} for r, p, e in parsed]
        (args.out / "input-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.out / "input-accounting.json").write_text(json.dumps(input_accounting(rows, plan), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0 if all(p or r.exclusion for r, p, _ in parsed) else 1
    report = args.out / f"처리결과_{stamp}.xlsx"
    summary = args.out / f"처리결과_{stamp}.json"
    def save():
        summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        write_report(report, sheets, layouts, results)
        accounting = input_accounting(rows, results)
        (run_dir / 'input-accounting.json').write_text(json.dumps(accounting, ensure_ascii=False, indent=2), encoding='utf-8')
    save()  # Record total/remaining input even before a browser starts.
    need_browser = any(p and p.key not in manifest and p.key not in ai_manifest for _, p, _ in parsed)
    if args.original_method == 'ops' and need_browser:
        from .ops_client import configured
        if args.source == 'kipris':
            raise ValueError('--original-method ops는 Espacenet 원문용이며 --source kipris와 함께 사용하지 않습니다.')
        if not configured():
            raise ValueError('OPS API 키 미설정. 로컬에서 scripts/run_with_ops.py를 사용하거나 EPO_OPS_KEY/EPO_OPS_SECRET을 설정하세요.')
    context = browser_session(args) if need_browser else nullcontext(None)
    browser_error = None
    context_entered = False
    try:
        page = context.__enter__()
        context_entered = True
    except Exception as exc:
        page = None
        browser_error = "브라우저 시작 실패: " + str(exc)
    try:
        for index, (row, patent, error) in enumerate(parsed, 1):
            h, width = layouts[row.sheet]
            result = {"sheet": row.sheet, "row": row.index, "input": row.value, "status": "실패",
                      "input_role":row.role, "input_role_source":row.role_source,
                      "normalized_input":patent.key if patent else None, "search_query":patent.query if patent else None,
                      "report_row":row.index + (1 if h < 0 else 0), "report_start_column":width + 1}
            if row.exclusion:
                result.update(status='제외', note=row.exclusion, complete_reference=False)
                results.append(result)
                save()
                print(f"[{index}/{len(parsed)}] 제외: {row.sheet} 행 {row.index} | {row.exclusion}", flush=True)
                continue
            try:
                if error:
                    raise ValueError(error)
                cache_key = (patent.key, patent.role)
                if cache_key in cache:
                    result.update(cache[cache_key])
                    result["note"] += " | 중복 입력: 기존 생성 결과 재사용"
                else:
                    work = run_dir / f"{index:05d}-{patent.key}"
                    work.mkdir()
                    if patent.key in ai_manifest:
                        from .ai_fallback import from_ai_packet
                        parts = from_ai_packet(patent, ai_manifest[patent.key], args.ai_manifest.parent, work)
                    elif patent.key in manifest:
                        parts = from_manifest(patent, manifest[patent.key], args.manifest.parent)
                    else:
                        if browser_error:
                            raise CollectionError(browser_error)
                        parts = (espacenet_collector.collect_original_only(page, patent, work, args)
                            if args.original_only else collect(page, patent, work, args))
                        time.sleep(args.delay)
                    filename = parts.publication.filename
                    resolved_key = (parts.publication.key, 'publication')
                    if resolved_key in cache:
                        success = dict(cache[resolved_key])
                        success['note'] += ' | 같은 공보의 입력 표기 변형: 결과 재사용'
                    else:
                        if args.original_only:
                            output, stats = copy_original_unique(parts.original, args.out / '원문만' / filename, parts.original_pages)
                        else:
                            output, stats = merge_unique(parts.biblio, parts.original, args.out / filename, parts.original_pages)
                        filename = output.name
                        note = parts.source + " | " + parts.verification
                        if filename != parts.publication.filename:
                            note += " | 동일 파일명 존재: " + filename + "으로 저장"
                        site_mode = parts.translation_type == 'site_machine_translation'
                        ai_mode = parts.translation_type in ('ai_translation','ai_summary')
                        ai_status = 'AI 번역 보완' if parts.translation_type == 'ai_translation' else 'AI 요약 보완'
                        success = dict(status="원문만" if args.original_only else ('사이트 기계번역 보완' if site_mode else (ai_status if ai_mode else "생성 완료")), filename=filename, **stats,
                            output_path=str(output),
                            publication=parts.publication.key, source=parts.source, biblio_url=parts.biblio_url,
                            original_url=parts.original_url, note=note,
                            result_type='original_only' if args.original_only else ('site_machine_translated_reference' if site_mode else ('ai_assisted_reference' if ai_mode else 'official_reference')),
                            material_type='original_only' if args.original_only else parts.translation_type,
                            generation_status='완료', review_status='검수 대기', final_review_complete=False,
                            official_materials_complete=not args.original_only and not ai_mode and not site_mode,
                            complete_reference=False, missing_fields=list(parts.missing_fields),
                            translation_type=parts.translation_type,
                            ai_provenance=({k:parts.ai_provenance[k] for k in ('bibliography','bibliography_note')} if site_mode else parts.ai_provenance),
                            site_translation_provenance=parts.ai_provenance if site_mode else None,
                            biblio_path=str(parts.biblio.resolve()) if parts.biblio else None, original_path=str(parts.original.resolve()),
                            biblio_sha256=sha256(parts.biblio) if parts.biblio else None, original_sha256=sha256(parts.original))
                        success['note'] += ' | PDF 생성 완료; 최종 시각 검수 대기'
                        success['review_packet'] = str(create_packet(success, work / 'final-review.json'))
                        cache[resolved_key] = success
                    cache[cache_key] = success
                    result.update(success)
            except HumanWaitTimeout as exc:
                result['note'] = str(exc)
                browser_error = "사용자 확인 중단으로 후속 온라인 수집 미실행: " + str(exc)
            except kipris_collector.TranslationRequired as exc:
                result.update(status='번역 검토 대기', complete_reference=False,
                    note=str(exc), diagnostics=exc.diagnostics,
                    error_code='TRANSLATION_REVIEW_REQUIRED',
                    review_packet=exc.diagnostics[0]['review_packet'])
            except IdentityReviewRequired as exc:
                result.update(status='원문 식별 검수 대기',complete_reference=False,
                    note=str(exc),diagnostics=exc.diagnostics,
                    error_code='ORIGINAL_IDENTITY_REVIEW_REQUIRED',
                    review_packet=exc.diagnostics[0]['review_packet'])
            except Exception as exc:
                result["note"] = str(exc)
                result['complete_reference'] = False
                if getattr(exc, 'diagnostics', None):
                    result['diagnostics'] = exc.diagnostics
                    result['error_code'] = exc.diagnostics[0]['code']
                    result['missing_fields'] = sorted({f for d in exc.diagnostics for f in d.get('missing_fields',[])})
            if patent and result.get('output_path'):
                role_label = '출원번호' if row.role == 'application' else '공보번호'
                result['note'] += ' | 입력번호 유형: ' + role_label
            if patent and patent.key in getattr(args,'download_metrics',{}):
                result['download_metrics'] = dict(args.download_metrics[patent.key])
            results.append(result)
            save()  # Resume evidence and results survive subsequent item failures.
            print(f"[{index}/{len(parsed)}] {result['status']}: {row.value}", flush=True)
    finally:
        if context_entered:
            context.__exit__(None, None, None)
    if args.zip:
        has_site_translation = any(isinstance(v,dict) and v.get('translation_type')=='site_machine_translation' for v in ai_manifest.values())
        archive_prefix = '원문만' if args.original_only else ('번역보완참증' if has_site_translation else ('AI보완참증' if ai_manifest else '참증'))
        with zipfile.ZipFile(args.out / f"검수대기_{archive_prefix}_{stamp}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr('검수안내.txt', '이 ZIP은 PDF 생성 결과입니다. 최종 시각 검수가 완료되지 않았습니다. 결과표의 자료 유형과 검수 상태를 확인하세요.')
            for path in sorted({r['output_path'] for r in results if r.get('output_path') and r['status'] != '실패'}):
                target = Path(path)
                z.write(target, target.relative_to(args.out).as_posix())
            z.write(report, report.name)
            z.write(summary, summary.name)
    successes = sum(r["status"] == "성공" for r in results)
    originals = sum(r['status'] == '원문만' for r in results)
    ai_assisted = sum(r.get('result_type') == 'ai_assisted_reference' for r in results)
    site_translated = sum(r.get('result_type') == 'site_machine_translated_reference' for r in results)
    failures = sum(r['status'] == '실패' for r in results)
    pending = sum(r['status'] == '번역 검토 대기' for r in results)
    identity_pending = sum(r['status'] == '원문 식별 검수 대기' for r in results)
    excluded = sum(r['status'] == '제외' for r in results)
    official_generated = sum(r.get('material_type') == 'official' for r in results)
    final_review_pending = sum(r.get('review_status') == '검수 대기' for r in results)
    accounted = official_generated + originals + ai_assisted + site_translated + failures + pending + identity_pending + excluded
    if accounted != len(rows) or len(results) != len(rows):
        raise ValueError('입력 행과 처리결과 집계가 일치하지 않습니다.')
    print(json.dumps({"input_rows":len(rows), "recorded_rows":len(results), "excluded":excluded, "accounting":str(run_dir / 'input-accounting.json'),
        "success": successes, "official_generated":official_generated, "generated":sum(bool(r.get('output_path')) for r in results),
        "final_review_pending":final_review_pending, "final_review_complete":0,
        "original_only": originals, 'ai_assisted':ai_assisted, 'site_translated':site_translated, "failed": failures,
        "translation_pending": pending, "identity_pending":identity_pending, "output_directory": str(args.out), "report": str(report),
        "files": sorted({r["output_path"] for r in results if r.get('output_path') and r['status'] != '실패'})}, ensure_ascii=False))
    return 0 if failures == 0 and pending == 0 and identity_pending == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(run(parser().parse_args()))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
