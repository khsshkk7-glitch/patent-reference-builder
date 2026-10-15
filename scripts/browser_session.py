"""Bounded retries and explicit human-assisted recovery; no CAPTCHA bypass."""
from contextlib import contextmanager
from pathlib import Path
import time
from urllib.parse import urlparse


class CollectionError(RuntimeError):
    pass


class HumanRequired(CollectionError):
    pass


class HumanWaitTimeout(HumanRequired):
    pass


@contextmanager
def browser_session(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = None
        if args.cdp:
            if urlparse(args.cdp).hostname not in ("127.0.0.1", "localhost", "::1"):
                raise ValueError("CDP는 로컬 브라우저에만 연결하세요.")
            browser = pw.chromium.connect_over_cdp(args.cdp)
            context = browser.contexts[0] if browser.contexts else browser.new_context(accept_downloads=True)
            owned = False
        elif args.profile:
            context = pw.chromium.launch_persistent_context(str(Path(args.profile).resolve()), headless=not args.headed,
                accept_downloads=True, locale="ko-KR", channel=args.channel or None)
            owned = True
        else:
            browser = pw.chromium.launch(headless=not args.headed, channel=args.channel or None)
            context = browser.new_context(accept_downloads=True, locale="ko-KR")
            owned = True
        context.set_default_timeout(args.timeout * 1000)
        page = context.new_page()
        try:
            yield page
        finally:
            page.close()
            if owned:
                context.close()
                if browser:
                    browser.close()
            # The attached user's browser and pre-existing tabs remain open.


def navigate(page, url, attempts=3):
    for attempt in range(attempts):
        try:
            response = page.goto(url, wait_until="domcontentloaded")
            if response and response.status in (401, 403, 429):
                raise HumanRequired(f"HTTP {response.status}: 접근 제한 또는 사용자 확인 필요")
            if response and response.status >= 500:
                raise CollectionError(f"서버 오류 {response.status}")
            return
        except HumanRequired:
            raise
        except Exception as exc:
            if attempt + 1 == attempts:
                raise CollectionError(f"탐색 재시도 소진: {type(exc).__name__}") from exc
            time.sleep(min(2 ** attempt, 8))


def checkpoint(page, args, message):
    if not args.interactive:
        raise HumanRequired(message + " (--headed --interactive 또는 검토된 manifest로 재개)")
    print(message, flush=True)
    print("브라우저에서 해당 작업을 완료한 뒤 제한 시간 내 Enter를 누르세요. 취소: q", flush=True)
    # Daemon reader lets unattended jobs time out rather than hang indefinitely.
    import threading
    import queue
    responses = queue.Queue()
    def read():
        try:
            responses.put(input())
        except EOFError:
            responses.put("q")
    threading.Thread(target=read, daemon=True).start()
    try:
        answer = responses.get(timeout=args.human_timeout)
    except queue.Empty as exc:
        # Caller stops this batch to avoid leaving another stdin reader behind.
        raise HumanWaitTimeout("사용자 확인 대기 시간 초과; --manifest로 재개하세요.") from exc
    if answer.strip().lower() == "q":
        raise HumanRequired("사용자가 확인을 취소했습니다.")


def visible_one(page, selectors):
    for selector in selectors:
        loc = page.locator(selector)
        visible = [loc.nth(i) for i in range(loc.count()) if loc.nth(i).is_visible()]
        if len(visible) == 1:
            return visible[0]
    raise CollectionError("페이지 구조 변경 또는 필요한 요소 없음: " + " | ".join(selectors))


def assert_official_url(url, source):
    host = (urlparse(url).hostname or "").lower()
    suffixes = ("espacenet.com", "epo.org") if source == "Espacenet" else ("kipris.or.kr", "kipo.go.kr", "k-pis.or.kr")
    if urlparse(url).scheme != "https" or not any(host == s or host.endswith("." + s) for s in suffixes):
        raise CollectionError("공식 HTTPS 출처 URL이 아닙니다.")
