"""KIPRIS search and configurable KPA/official-publication adapter.

Selectors are supplied from the current inspected UI; do not guess private APIs.
"""
import re
from .browser_session import navigate, checkpoint, CollectionError, assert_official_url
from .collector_common import Collected, print_biblio
from .input_parser import extract, resolve
from .pdf_merger import inspect_pdf


START = "https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent"


def collect_configured(page, patent, work, args):
    if patent.country != "KR":
        raise CollectionError("KIPRIS 자동 폴백 대상은 KR입니다.")
    navigate(page, START, args.retries)
    config = args.selectors.get("kipris", {})
    # KIPRIS changes popup routes and embedded PDF viewers. Support an explicit
    # observed selector profile instead of claiming undocumented endpoints work.
    required = ("search_input", "search_button", "result", "kpa_button", "biblio_root", "publication", "abstract", "original_button", "page_count", "download")
    if not all(config.get(key) for key in required):
        raise CollectionError("KIPRIS 화면 선택자 프로필 필요. references/browser-recovery.md에 따라 현재 화면을 확인하여 --selectors를 제공하거나 manifest로 재개하세요.")
    page.locator(config["search_input"]).fill(patent.key)
    page.locator(config["search_button"]).click()
    result = page.locator(config["result"])
    result.wait_for(state="visible")
    if result.count() != 1:
        raise CollectionError("KIPRIS 검색 결과가 단일하지 않습니다.")
    result.click()
    if config.get("kpa_popup", True):
        with page.expect_popup() as popup:
            page.locator(config["kpa_button"]).click()
        kpa = popup.value
    else:
        page.locator(config["kpa_button"]).click()
        kpa = page
    try:
        kpa.locator(config["publication"]).wait_for(state="visible")
        publication = resolve(patent, extract(kpa.locator(config["publication"]).inner_text(), country="KR"))
        biblio_url = kpa.url
        assert_official_url(biblio_url, "KIPRIS")
        biblio = work / "biblio.pdf"
        print_biblio(kpa, config["biblio_root"], kpa.locator(config["abstract"]).inner_text(), biblio, config.get("hide", []))
    finally:
        if kpa != page:
            kpa.close()
    page.locator(config["original_button"]).click()
    text = page.locator(config["page_count"]).inner_text()
    match = re.fullmatch(config.get("page_count_pattern", r"\s*(\d+)\s*"), text)
    if not match:
        raise CollectionError("KIPRIS 원문 전체 페이지 수 확인 실패")
    count = int(match[1])
    original_url = page.url
    original = work / "original.pdf"
    with page.expect_download() as event:
        page.locator(config["download"]).click()
    event.value.save_as(original)
    reader = inspect_pdf(original)
    if len(reader.pages) != count:
        raise CollectionError("원문 총 페이지 수 불일치")
    resolve(publication, extract(reader.pages[0].extract_text() or "", country="KR"))
    return Collected(publication, biblio, original, count, "KIPRIS", biblio_url, original_url,
                     "KPA 공보번호·원문 표지·사이트 전체 페이지 수 대조; 최종 시각 검수 필요")


def national_number(patent):
    return ('10' + patent.number) if len(patent.number) == 11 else patent.number


def domestic_number_matches(text, number, kind):
    # KIPRIS domestic registration numbers append a four-digit serial suffix.
    suffix = r'(?:0000)?' if kind.startswith('B') else ''
    return bool(re.search(r'(?<!\d)' + re.escape(number) + suffix + r'(?!\d)', text))


def official_cover_text(path):
    # Older KIPRIS originals use KSCms-UHC-H, unsupported by pypdf extraction.
    # PDFium reads the original bytes; it does not alter or translate the PDF.
    import pypdfium2
    with pypdfium2.PdfDocument(path) as document:
        page = document[0]
        try:
            textpage = page.get_textpage()
            try:
                return textpage.get_text_range()
            finally:
                textpage.close()
        finally:
            page.close()


def collect(page, patent, work, args):
    """Default adapter inspected on 2026-10-15; KPA then domestic full PDF."""
    if args.selectors.get('kipris'):
        return collect_configured(page, patent, work, args)
    if patent.country != 'KR':
        raise CollectionError('KIPRIS 자동 폴백 대상은 KR입니다.')
    if patent.role == 'application':
        raise CollectionError('출원번호는 공보 후보를 확인한 뒤 manifest 매핑으로 재개하세요.')
    navigate(page, START, args.retries)
    dialog = page.locator('#modalSearchDetail[aria-hidden="false"]')
    if dialog.count() and dialog.is_visible():
        dialog.get_by_role('button', name='닫기', exact=True).click()
    page.locator('#patentTabPannel').get_by_role('link', name=re.compile(r'^KPA')).click()
    number = national_number(patent)
    page.locator('#queryText').fill(number)
    page.get_by_role('button', name='검색', exact=True).click()
    page.wait_for_function('''() => {
      const result=document.querySelector('#resultSection');
      return result && (result.querySelector('article') ||
        (result.querySelector('.nodata-area') && result.innerText.includes('검색결과가 없습니다')));
    }''')
    if page.locator('#resultSection .nodata-area').count():
        raise CollectionError(f'KPA에서 {number}의 검색결과가 없습니다. 다른 공보로 대체하지 않고 동일 공보 원문·AI 보완 경로를 확인하세요.')
    page.locator('#resultSection article').first.wait_for(state='visible')
    candidates = []
    articles = page.locator('#resultSection article')
    for i in range(articles.count()):
        article = articles.nth(i)
        # Same digits may identify an unrelated application: inspect publication field only.
        field = article.locator('li').filter(has=page.locator('[data-lang-id="srlt.kpa.pn"]'))
        if field.count() == 1 and re.search(r'(?<!\d)' + number + r'(?!\d)', field.inner_text()):
            candidates.append(article)
    if len(candidates) != 1:
        raise CollectionError('KPA 공고번호 정확 일치 후보가 단일하지 않습니다.')
    candidates[0].get_by_role('button', name=re.compile(r'^\[\d+\]')).click()
    pane = page.locator('#mainResultDetail')
    pub = pane.locator('tr').filter(has_text='공고번호(일자)')
    pub.wait_for(state='visible')
    pub_text = pub.locator('td').inner_text()
    publication = resolve(patent, extract(pub_text, country='KR'))
    app_text = pane.locator('tr').filter(has_text='출원번호(일자)').locator('td').inner_text()
    app_number = re.search(r'\d{13}', app_text)
    if not app_number:
        raise CollectionError('KPA 출원번호 연결을 확인할 수 없습니다.')
    abstract = '\n'.join(pane.locator('p.txt').all_inner_texts())
    biblio = work / 'biblio.pdf'
    biblio_url = page.url
    # The site's print action opens its own clean KPA print page.
    with page.expect_popup() as popup:
        pane.locator('a.btn-print').click()
    print_page = popup.value
    try:
        print_page.wait_for_load_state('domcontentloaded')
        print_page.wait_for_function('(text) => document.body && document.body.innerText.includes(text)', arg=abstract[:60])
        (work / 'kpa-print.html').write_text(print_page.content(), encoding='utf-8')
        print_biblio(print_page, 'body', abstract, biblio, scale=0.9)
    finally:
        print_page.close()
    from playwright.sync_api import TimeoutError as BrowserTimeout
    try:
        return collect_domestic(page, publication, app_number[0], number, biblio, biblio_url, work, args)
    except BrowserTimeout as exc:
        # Preserve the source evidence before leaving the failed KIPRIS pane.
        (work / 'kipris-domestic-error.txt').write_text(str(exc), encoding='utf-8')
        (work / 'kipris-domestic-failure.html').write_text(page.content(), encoding='utf-8')
        page.screenshot(path=str(work / 'kipris-domestic-failure.png'))
        if getattr(args, 'no_fallback', False):
            raise CollectionError('KIPRIS 직접 원문 수집 실패; --no-fallback으로 Espacenet 대체 금지') from exc
        return recover_original(page, publication, biblio, biblio_url, work, args)


def recover_original(page, publication, biblio, biblio_url, work, args):
    from .espacenet_collector import collect_original
    fallback = work / 'espacenet-original'
    fallback.mkdir(exist_ok=True)
    print('KIPRIS 국내 전문 연결 지연/실패: KPA 인쇄본을 유지하고 동일 공보의 Espacenet 원문으로 복구합니다.', flush=True)
    resolved, original, count, url = collect_original(page, publication, fallback, args)
    resolve(publication, [resolved])
    return Collected(publication, biblio, original, count, 'KIPRIS + Espacenet', biblio_url, url,
        'KPA 공보번호·종별과 Espacenet 공식 원문 공보번호·종별 일치; 전문 뷰어 총 페이지 수 대조; KIPRIS 국내 연결 실패 후 복구. 최종 시각 검수 필요')


def collect_domestic(page, publication, application_number, number, biblio, biblio_url, work, args):
    # Select domestic record by the application number obtained from this KPA.
    page.locator('#patentTabPannel').get_by_role('link', name=re.compile(r'^국내')).click()
    articles = page.locator('#resultSection article[id="divViewSel"]')
    articles.first.wait_for(state='visible')
    page.wait_for_load_state('networkidle')
    match = articles.filter(has_text=application_number)
    if match.count() != 1:
        raise CollectionError('KPA에 대응하는 국내 출원기록이 단일하지 않습니다.')
    match.get_by_role('button', name=re.compile(r'^\[\d+\]')).click()
    pane = page.locator('#mainResultDetail')
    label = '등록번호(일자)' if publication.kind.startswith('B') else '공개번호(일자)'
    domestic = pane.locator('tr').filter(has=page.get_by_role('rowheader', name=label, exact=True))
    domestic.wait_for(state='visible')
    if not domestic_number_matches(domestic.inner_text(), number, publication.kind):
        raise CollectionError('국내 원문 공보번호가 KPA와 일치하지 않습니다.')
    pane.get_by_role('button', name=re.compile(r'^(?:공고|등록)전문$') if publication.kind.startswith('B') else '공개전문', exact=True).click()
    iframe = pane.locator('iframe')
    iframe.wait_for(state='attached')
    src = iframe.get_attribute('src')
    from urllib.parse import parse_qs, urlparse, unquote
    file_url = parse_qs(urlparse(src).query).get('file', [''])[0].split('#')[0]
    if not file_url.startswith('blob:https://www.kipris.or.kr/'):
        raise CollectionError('공식 전문 뷰어 PDF 연결이 변경되었습니다. 선택자 프로필 또는 manifest로 재개하세요.')
    frame = iframe.element_handle().content_frame()
    if frame is None:
        raise CollectionError('전문 PDF 뷰어 프레임 준비 실패')
    frame.wait_for_function(r"""() => {
      const el=document.querySelector('#numPages');
      const n=el && el.textContent.match(/\d+/g);
      return n && n.length===1 && Number(n[0])>0;
    }""")
    page_text = frame.locator('#numPages').inner_text()
    numbers = re.findall(r'\d+', page_text)
    if len(numbers) != 1 or int(numbers[0]) < 1:
        raise CollectionError('전문 뷰어의 전체 페이지 수가 아직 준비되지 않았습니다.')
    count = int(numbers[0])
    # Download the exact blob displayed by the official viewer, never reprint it.
    import base64
    data = page.evaluate("""async url => {
      const r=await fetch(url); if(!r.ok) throw new Error('PDF fetch failed');
      const b=await r.blob(); return await new Promise((ok,fail)=>{
        const reader=new FileReader(); reader.onload=()=>ok(reader.result.split(',')[1]);
        reader.onerror=fail; reader.readAsDataURL(b);
      });
    }""", file_url)
    original = work / 'original.pdf'
    original.write_bytes(base64.b64decode(data))
    reader = inspect_pdf(original)
    if len(reader.pages) != count:
        raise CollectionError('원문 전체 페이지 수 불일치')
    # Korean official cover separates country/kind/number across different fields.
    cover = official_cover_text(original)
    compact = re.sub(r'\s+', '', cover)
    display_number = '10-' + publication.number[:4] + '-' + publication.number[4:] if len(publication.number)==11 else publication.number[:2]+'-'+publication.number[2:]
    if cover.strip() and display_number not in compact and number not in compact:
        raise CollectionError('원문 표지 번호가 요청한 공보와 일치하지 않습니다.')
    kinds = re.findall(r'공보\s*\(\s*([AB]\d*)\s*\)', cover)
    if kinds and publication.kind not in kinds:
        raise CollectionError('원문 표지의 공개/등록 종류 코드가 요청과 일치하지 않습니다.')
    return Collected(publication, biblio, original, count, 'KIPRIS', biblio_url, page.url,
        'KPA 공고번호·출원번호로 국내 공보 연결, 전문 뷰어 전체 페이지 수 대조; 최종 시각 검수 필요')
