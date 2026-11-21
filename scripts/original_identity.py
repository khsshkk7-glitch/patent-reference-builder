"""Keep unidentifiable originals pending; reject identifiable mismatches."""
import json
import re
from pathlib import Path
from .browser_session import CollectionError
from .input_parser import clean, conflicting_korean_prefixes, extract, korean_display_number, korean_right
from .pdf_merger import sha256, inspect_pdf


class DocumentIdentityMismatch(CollectionError):
    pass


class IdentityReviewRequired(CollectionError):
    def __init__(self, publication, packet):
        self.diagnostics = [{'code':'ORIGINAL_IDENTITY_REVIEW_REQUIRED',
            'publication':publication.key,'review_packet':str(packet.resolve())}]
        super().__init__('원문 표지의 공보번호·종별을 자동 식별할 수 없습니다. 원문 식별 검수 후 재개하세요: '+str(packet.resolve()))


_KR_COVER_FIELD = re.compile(r'\(11\)\s*(?:공개|공고|등록)\s*번호(.*?)(?=\((?!24\)|43\)|45\))\d{2}\)|(?:출원|우선권)\s*번호|\Z)', re.S)
_KR_COVER_NUMBER = re.compile(r'(?<!\d)(?:10|20)(?:\s*-\s*(?:\d{4}\s*-\s*)?\d{7}|\d{11}|\d{7})(?!\d)')
_KR_COVER_KIND = re.compile(r'\(12\)[^\r\n]*?공보\s*\(\s*([ABUY]\d?)\s*\)')


def check_korean_cover(publication, text, *, require_readable_field=False):
    """Check the authoritative Korean cover fields without accepting an application number."""
    text = clean(text)
    fields = _KR_COVER_FIELD.findall(text)
    numbers = {re.sub(r'\D', '', m[0]) for field in fields for m in _KR_COVER_NUMBER.finditer(field)}
    kinds = set(_KR_COVER_KIND.findall(text))
    expected_display = korean_display_number(publication)
    expected = re.sub(r'\D', '', expected_display)
    if (numbers and numbers != {expected}) or (kinds and kinds != {publication.kind}):
        observed = ', '.join(sorted(numbers | kinds))
        raise DocumentIdentityMismatch(f'한국 원문 표지의 (11) 공보번호 또는 (12) 종별 불일치: '
                                       f'요청 {expected_display} {publication.kind}, 표지 {observed}')
    if require_readable_field and fields and not numbers:
        raise CollectionError('한국 원문 표지의 (11) 공보번호를 읽지 못했습니다. (21) 출원번호는 공보번호로 사용하지 않습니다.')
    return bool(numbers and kinds)


def check_korean_pdf_cover(publication, path):
    if publication.country == 'KR':
        check_korean_cover(publication, official_cover_text(path))


def official_cover_text(path):
    # PDFium also handles older Korean KSCms-UHC-H covers.
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


def verify_original(publication, original, count, work, source, biblio_url, original_url):
    reader = inspect_pdf(original)
    if len(reader.pages) != count:
        raise CollectionError('원문 전체 페이지 수 불일치')
    try:
        text = reader.pages[0].extract_text() or ''
    except Exception:
        # Encoding failure is not identity evidence. Preserve the PDF for review.
        text = ''
    if publication.country == 'KR':
        # Read Korean field labels even when pypdf cannot decode the original font.
        text = official_cover_text(original) or text
        if check_korean_cover(publication, text):
            return
        conflict = next(conflicting_korean_prefixes(text), None)
        if conflict:
            raise DocumentIdentityMismatch(f'한국 원문 표지의 권리 접두부 {conflict[0]}와 종별 {conflict[1]} 충돌')
    identifiers = [] if publication.country == 'KR' and _KR_COVER_FIELD.search(clean(text)) else extract(text)
    if identifiers:
        same = [p for p in identifiers if p.country==publication.country and p.number==publication.number
                and (p.country != 'KR' or korean_right(p) in ('', korean_right(publication)))]
        exact = any(p.kind==publication.kind for p in same)
        if exact and all(p in same and p.kind==publication.kind for p in identifiers):
            return
        # Matching digits without a readable kind are insufficient evidence,
        # but are not an identified conflicting publication either.
        if not exact and (not same or any(p.kind for p in same)):
            raise DocumentIdentityMismatch('원문 표지 공보번호·국가·종별 불일치: 요청 '+publication.key+
                ', 표지 '+', '.join(p.key for p in identifiers))
        # Multiple distinct IDs may be front-page citations or a wrong cover
        # citing the requested document. Text extraction alone cannot decide.
    work = Path(work)
    (work/'identity-cover.txt').write_text(text, encoding='utf-8')
    entry = dict(publication=publication.key,source=source,
        biblio_url=biblio_url,original_url=original_url,
        original_pdf=str(Path(original).resolve()),original_sha256=sha256(original),
        original_pages=count,viewer_pages=count,
        identity_verified=False,english_abstract_verified=False,
        full_document_verified=False,layout_verified=False,verification_note='')
    biblio = work/'biblio.pdf'
    if biblio.exists():
        entry.update(biblio_pdf=str(biblio.resolve()),biblio_sha256=sha256(biblio))
    packet = work/'identity-review.json'
    packet.write_text(json.dumps({publication.key:entry},ensure_ascii=False,indent=2),encoding='utf-8')
    raise IdentityReviewRequired(publication,packet)
