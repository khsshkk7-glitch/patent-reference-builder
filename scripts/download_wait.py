"""Wait for a real browser download; stop repeated human verification prompts."""
import re
import time
from urllib.parse import parse_qs, urlparse
from .browser_session import HumanWaitTimeout


def wait_for_download(page, trigger, href, wait_seconds, interactive):
    from playwright.sync_api import TimeoutError as BrowserTimeout
    target = urlparse(href)
    expected = parse_qs(target.query)
    downloads, responses = [], []

    def downloaded(item):
        downloads.append(item)

    def responded(response):
        url = urlparse(response.url)
        params = parse_qs(url.query)
        if (url.hostname == target.hostname and url.path == target.path
                and all(params.get(key) == expected.get(key) for key in ('CC', 'NR', 'KC'))
                and 'html' in response.headers.get('content-type', '').lower()):
            responses.append(response)

    page.on('download', downloaded)
    page.on('response', responded)
    started = time.monotonic()
    prompts = 0
    try:
        trigger()
        while time.monotonic() - started < wait_seconds:
            if downloads:
                return downloads[0]
            # Inspect only the public response body, never record CAPTCHA answers
            # or request headers/POST bodies.
            while responses:
                response = responses.pop(0)
                body = response.text()
                if re.search(r'Espacenet verification|Please enter the digits', body, re.I):
                    prompts += 1
                    if prompts >= 3:
                        raise HumanWaitTimeout(
                            '같은 문헌의 보안문자 확인 화면이 반복되어 중단했습니다. '
                            '반복 입력하지 말고 사이트 응답/세션을 확인하세요. 다운로드 미완료.'
                        )
            page.wait_for_timeout(250)
        if interactive:
            raise HumanWaitTimeout('보안문자 사용자 확인 대기 시간 초과; 다운로드 미완료. 검토 manifest로 재개하세요.')
        raise BrowserTimeout('공식 다운로드 버튼에서 파일 수신 대기 시간 초과')
    finally:
        page.remove_listener('download', downloaded)
        page.remove_listener('response', responded)
