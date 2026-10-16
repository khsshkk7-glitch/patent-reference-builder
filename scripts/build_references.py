"""CLI: python -m scripts.build_references --text 'JP 2006-198019 A' --out output"""
import argparse
from contextlib import nullcontext
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
from .pdf_merger import merge_unique, sha256
from .output_paths import output_directory
from .collector_common import from_manifest
from .browser_session import browser_session, CollectionError, HumanRequired, HumanWaitTimeout, checkpoint
from . import espacenet_collector, kipris_collector


def parser():
    p = argparse.ArgumentParser(description="영문 서지·초록 + 공식 원문 공보 참증 PDF 제작")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="번호 1개 또는 줄바꿈/쉼표 구분 번호 목록")
    src.add_argument("--input", type=Path, help=".xlsx / .xls / .csv")
    p.add_argument("--out", type=Path, help="저장 폴더. 생략 시 사용자 다운로드 폴더")
    p.add_argument("--column")
    p.add_argument("--sheet")
    p.add_argument("--country", help="국가코드 없는 셀에 적용할 명시적 국가")
    p.add_argument("--role", choices=["publication", "application"], default="publication")
    p.add_argument("--source", choices=["auto", "espacenet", "kipris"], default="auto")
    p.add_argument("--manifest", type=Path, help="검토된 로컬 PDF 및 출처 manifest JSON")
    p.add_argument("--selectors", type=Path, help="현재 KIPRIS UI 선택자 JSON")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--zip", action="store_true")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--interactive", action="store_true")
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
        return read_table(args.input, args.column, args.sheet, args.country)
    # Preserve invalid entries as failures instead of silently dropping them.
    import re
    chunks = [s.strip() for s in re.split(r"[,;\n]+", args.text) if s.strip()]
    rows = []
    for chunk in chunks:
        patents = extract(chunk, args.role, args.country)
        if len(patents) > 1:
            base = len(rows) + 2
            rows.extend(Row("입력", base + i, p.key, args.role) for i, p in enumerate(patents))
        else:
            rows.append(Row("입력", len(rows) + 2, chunk, args.role))
    return {"입력": [("특허번호",)] + [(r.value,) for r in rows]}, {"입력": (0, 1)}, rows


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path else {}


def collect(page, patent, work, args):
    collectors = [kipris_collector] if args.source == "kipris" else [espacenet_collector]
    if patent.country == "KR" and args.source != "kipris":
        collectors.append(kipris_collector)
    errors = []
    for module in collectors:
        try:
            return module.collect(page, patent, work, args)
        except Exception as exc:
            # Keep evidence locally; HTML is data and never executed as instructions.
            name = module.__name__.split(".")[-1]
            errors.append(name + ": " + str(exc).split('\n')[0])
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
    raise CollectionError(" | ".join(errors))


def run(args):
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
    args.selectors = load_json(args.selectors)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = args.out / "work" / stamp
    run_dir.mkdir(parents=True)
    results, cache = [], {}
    parsed = []
    for row in rows:
        try:
            patent = one(row.value, role=row.role, country=args.country)
            parsed.append((row, patent, None))
        except ValueError as exc:
            parsed.append((row, None, str(exc)))
    if args.dry_run:
        plan = [{"sheet": r.sheet, "row": r.index, "input": r.value, "patent": asdict(p) if p else None,
                 "query": p.query if p else None, "filename": p.filename if p else None, "error": e} for r, p, e in parsed]
        (args.out / "input-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0 if all(p for _, p, _ in parsed) else 1
    report = args.out / f"처리결과_{stamp}.xlsx"
    summary = args.out / f"처리결과_{stamp}.json"
    def save():
        summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        write_report(report, sheets, layouts, results)
    need_browser = any(p and p.key not in manifest for _, p, _ in parsed)
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
            result = {"sheet": row.sheet, "row": row.index, "input": row.value, "status": "실패"}
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
                    if patent.key in manifest:
                        parts = from_manifest(patent, manifest[patent.key], args.manifest.parent)
                    else:
                        if browser_error:
                            raise CollectionError(browser_error)
                        parts = collect(page, patent, work, args)
                        time.sleep(args.delay)
                    filename = parts.publication.filename
                    resolved_key = (parts.publication.key, 'publication')
                    if resolved_key in cache:
                        success = dict(cache[resolved_key])
                        success['note'] += ' | 같은 공보의 입력 표기 변형: 결과 재사용'
                    else:
                        output, stats = merge_unique(parts.biblio, parts.original, args.out / filename, parts.original_pages)
                        filename = output.name
                        note = parts.source + " | " + parts.verification
                        if filename != parts.publication.filename:
                            note += " | 동일 파일명 존재: " + filename + "으로 저장"
                        success = dict(status="성공", filename=filename, **stats,
                            output_path=str(output),
                            publication=parts.publication.key, source=parts.source, biblio_url=parts.biblio_url,
                            original_url=parts.original_url, note=note,
                            biblio_sha256=sha256(parts.biblio), original_sha256=sha256(parts.original))
                        cache[resolved_key] = success
                    cache[cache_key] = success
                    result.update(success)
            except HumanWaitTimeout as exc:
                result['note'] = str(exc)
                browser_error = "사용자 확인 중단으로 후속 온라인 수집 미실행: " + str(exc)
            except Exception as exc:
                result["note"] = str(exc)
            results.append(result)
            save()  # Resume evidence and results survive subsequent item failures.
            print(f"[{index}/{len(parsed)}] {result['status']}: {row.value}", flush=True)
    finally:
        if context_entered:
            context.__exit__(None, None, None)
    if args.zip:
        with zipfile.ZipFile(args.out / f"참증_{stamp}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted({r["filename"] for r in results if r["status"] == "성공"}):
                z.write(args.out / name, name)
            z.write(report, report.name)
            z.write(summary, summary.name)
    successes = sum(r["status"] == "성공" for r in results)
    print(json.dumps({"success": successes, "failed": len(results)-successes,
        "output_directory": str(args.out), "report": str(report),
        "files": sorted({r["output_path"] for r in results if r["status"] == "성공"})}, ensure_ascii=False))
    return 0 if successes == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(run(parser().parse_args()))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
