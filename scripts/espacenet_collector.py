"""Espacenet classic UI adapter. Fail closed if current UI differs."""
import re
from urllib.parse import urljoin, urlparse, parse_qs
from .input_parser import extract, resolve
from .collector_common import Collected, print_biblio, english_abstract
from .pdf_merger import inspect_pdf
from .browser_session import CollectionError, MetadataUnavailable, HumanRequired, HumanWaitTimeout, navigate
from .download_wait import wait_for_download
from .original_identity import verify_original


START = "https://worldwide.espacenet.com/advancedSearch?locale=en_EP"


def open_record(page, patent, args):
    navigate(page, START, args.retries)
    page.wait_for_load_state("load")
    field = "#apEditBox" if patent.role == "application" else "#pnEditBox"
    page.locator(field).fill(patent.key)
    page.get_by_role("button", name="Search", exact=True).click()
    page.locator('a[id^="publicationId"]').first.wait_for(state="visible")
    links = page.locator('a[id^="publicationId"]')
    if links.count() != 1:
        raise CollectionError("검색 결과가 여러 개입니다. 공보번호/종류 코드를 지정하세요.")
    links.first.click()
    page.locator("#pagebody h1").wait_for(state="visible")
    title = page.locator("#pagebody h1").inner_text()
    if patent.role == "application":
        # Do not silently select a publication from an application result/family.
        raise CollectionError("출원번호 검색 완료. 공보 매핑을 검토하고 manifest의 application/mapping_verified로 재개하세요.")
    publication = resolve(patent, extract(title))
    if not patent.kind:
        same_number = extract(title)
        for text in page.locator('#lessPublishedAs a, #morePublishedAs a').all_inner_texts():
            same_number.extend(extract(text))
        publication = resolve(patent, same_number)
    return publication


def inspect_bibliography(page, publication):
    """Record all observed gaps before choosing complete or original-only output."""
    page.locator("#pagebody .application.article").wait_for(state="visible")
    article = page.locator("#pagebody .application.article")
    heading = article.locator("h3").inner_text()
    abstract_ids = extract(heading)
    if not abstract_ids or resolve(publication, abstract_ids) != publication:
        raise CollectionError("다른 패밀리 문헌의 초록입니다. 동일 문헌 초록을 확인하세요.")
    # Source text excludes translation controls and the heading.
    abstract = article.evaluate("""el => {
      const c=el.cloneNode(true);
      c.querySelectorAll('h3,script,style,.noPrint,#languageSelectorContainer').forEach(e=>e.remove());
      return c.textContent.trim();
    }""")
    missing = []
    title = page.locator('#bookmarkTitle')
    if not title.count():
        title = page.locator('#pagebody > h3[lang="en"]')
    title_text = title.first.inner_text().strip() if title.count() else ''
    if not title_text or re.search(r'no title available', title_text, re.I):
        missing.append('title')
    for field, selector in (('inventors','#inventorsRow'), ('applicants','#applicantsRow')):
        value = page.locator(selector)
        if not value.count() or not value.inner_text().strip():
            missing.append(field)
    if not abstract.strip() or re.search(r'abstract not available', heading, re.I):
        missing.append('english_abstract')
    else:
        try:
            english_abstract(abstract)
        except CollectionError:
            # A Korean abstract is source material, not an English abstract.
            missing.append('english_abstract')
    return abstract, tuple(missing)


def collect(page, patent, work, args):
    publication = open_record(page, patent, args)
    abstract, missing = inspect_bibliography(page, publication)
    if missing:
        raise MetadataUnavailable(publication, page.url, missing,
            page.get_by_role('link', name='Original document', exact=True).count()>0)
    biblio_url = page.url
    biblio = work / "biblio.pdf"
    print_biblio(page, "#pagebody", abstract, biblio)
    target, count, original_url = download_original(page, publication, work, args)
    ops = original_url.startswith('https://ops.epo.org/')
    return Collected(publication, biblio, target, count, 'Espacenet + EPO OPS' if ops else 'Espacenet', biblio_url, original_url,
        ('OPS 공식 단일 페이지 PDF를 순서대로 조립; Espacenet 뷰어 총 페이지 수 대조. ' if ops else '')
        +"서지·초록 번호 및 공식 전체 다운로드 URL 종별 일치; 사이트 전체 페이지 수 대조. 최종 시각 검수 필요")


def collect_original(page, patent, work, args):
    """Exact official publication only; no English abstract requirement."""
    publication = open_record(page, patent, args)
    target, count, url = download_original(page, publication, work, args)
    return publication, target, count, url


def collect_original_only(page, patent, work, args):
    publication = open_record(page, patent, args)
    _, missing = inspect_bibliography(page, publication)
    biblio_url = page.url
    target, count, url = download_original(page, publication, work, args)
    ops = url.startswith('https://ops.epo.org/')
    return Collected(publication, None, target, count, 'Espacenet + EPO OPS' if ops else 'Espacenet', biblio_url, url,
        '원문 단독 수집; 영문 서지·초록이 결합된 완성 참증 아님; 공식 전문 URL·종별·전체 페이지 수 대조'
        + ('; OPS 공식 페이지 PDF 순서 조립' if ops else '')
        + ('; 화면 누락: '+', '.join(MetadataUnavailable.labels[k] for k in missing) if missing else ''), missing)


def download_original(page, publication, work, args):
    biblio_url = page.url
    original_link = page.get_by_role("link", name="Original document", exact=True)
    original_link.wait_for(state="visible")
    original_link.click()
    page.locator("#pagebody h1").wait_for(state="visible")
    resolve(publication, extract(page.locator("#pagebody h1").inner_text()))
    original_url = page.url
    # Capture source pagination before download. Never infer full length from downloaded length.
    page.locator('#navigationSelector option').first.wait_for(state="attached")
    body = page.locator('#navigationSelector').text_content()
    counts = re.findall(r"(?:\bof\s+|/\s*)(\d+)\b|\b(\d+)\s+pages\b", body, re.I)
    numbers = {int(a or b) for a, b in counts}
    if len(numbers) != 1:
        raise CollectionError("전문 전체 페이지 수를 확인하지 못했습니다. manifest로 검토 후 재개하세요.")
    count = numbers.pop()
    from .ops_client import OpsClient, configured
    method = getattr(args,'original_method','auto')
    if not hasattr(args,'download_metrics'):
        args.download_metrics = {}
    metrics = args.download_metrics[publication.key] = {'method':'browser','captcha_prompts':0,'status':'started'}
    if method == 'ops' or (method == 'auto' and configured()):
        metrics['method'] = 'EPO OPS'
        try:
            if not hasattr(args,'ops_client'):
                args.ops_client = OpsClient(timeout=args.timeout)
            result = args.ops_client.download(publication,work,expected_pages=count)
            verify_original(publication,result[0],count,work,'Espacenet + EPO OPS',biblio_url,result[2])
            metrics.update(status='downloaded',pages=count)
            return result
        except Exception:
            metrics['status']='failed'
            # A quota/auth/data failure must not silently switch to CAPTCHA.
            raise
    download = page.get_by_role("link", name=re.compile(r"^Download(?: full document| document)?$", re.I))
    if download.count() != 1:
        raise CollectionError("전체 문서 다운로드 버튼을 확인하지 못했습니다.")
    target = work / "original.pdf"
    href = urljoin(page.url, download.get_attribute('href') or '')
    params = parse_qs(urlparse(href).query)
    # The observed official Download link requests trueFull, not plainPage/covers.
    if params.get('flavour') != ['trueFull'] or params.get('CC') != [publication.country] or params.get('NR') != [publication.number + publication.kind] or params.get('KC') != [publication.kind]:
        raise CollectionError('전체 다운로드 URL의 문헌번호/종별 연결을 확인하지 못했습니다.')
    from .browser_session import assert_official_url
    assert_official_url(href, 'Espacenet')
    page.wait_for_load_state("load")
    # Keep the download in the actual browser session, including its normal
    # navigation and download handling, instead of a separate HTTP client.
    from playwright.sync_api import TimeoutError as BrowserTimeout
    interactive = getattr(args, "interactive", False)
    wait_seconds = args.human_timeout if interactive else args.timeout
    if interactive:
        print(f"[{publication.key}] 원문 다운로드: 보안문자가 표시되면 브라우저에서 직접 입력하고 Submit을 누르세요. "
              "파일 수신 후 자동으로 이어갑니다. 터미널 Enter는 필요 없습니다.", flush=True)
    try:
        def prompt(number):
            print(f'[{publication.key}] 보안문자 표시 {number}회: 열린 Chrome에서 입력 후 Submit을 누르세요. 같은 창에서 자동 재개합니다.',flush=True)
        received = wait_for_download(page, download.click, href, wait_seconds, interactive, metrics=metrics,on_prompt=prompt)
    except HumanWaitTimeout:
        (work / 'download-stopped.html').write_text(page.content(), encoding='utf-8')
        page.screenshot(path=str(work / 'download-stopped.png'))
        for index, frame in enumerate(page.frames):
            if frame is page.main_frame:
                continue
            try:
                # Only the visible prompt/error is retained; form answers aren't logged.
                text = frame.locator('body').inner_text(timeout=2000)
                (work / f'download-frame-{index}.txt').write_text(text, encoding='utf-8')
            except Exception:
                pass
        raise
    except BrowserTimeout as exc:
        for index, opened in enumerate(page.context.pages):
            if opened is page or opened.is_closed():
                continue
            try:
                (work / f"download-window-{index}.html").write_text(opened.content(), encoding="utf-8")
                opened.screenshot(path=str(work / f"download-window-{index}.png"))
            except Exception:
                pass
        error_type = HumanWaitTimeout if interactive else HumanRequired
        raise error_type(
            "공식 다운로드 버튼에서 파일 수신을 확인하지 못했습니다. "
            "열린 다운로드 창의 오류/사용자 확인 화면을 확인하거나 검토 manifest로 재개하세요."
        ) from exc
    if received.failure():
        raise CollectionError("전체 다운로드 실패: " + received.failure())
    received.save_as(str(target))
    r = inspect_pdf(target)
    if len(r.pages) != count:
        raise CollectionError("전체 페이지 수와 다운로드 PDF 불일치")
    verify_original(publication,target,count,work,'Espacenet',biblio_url,original_url)
    return target, count, original_url
