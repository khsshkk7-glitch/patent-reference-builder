"""Keep unidentifiable originals pending; reject identifiable mismatches."""
import json
from pathlib import Path
from .browser_session import CollectionError
from .input_parser import extract
from .pdf_merger import sha256, inspect_pdf


class DocumentIdentityMismatch(CollectionError):
    pass


class IdentityReviewRequired(CollectionError):
    def __init__(self, publication, packet):
        self.diagnostics = [{'code':'ORIGINAL_IDENTITY_REVIEW_REQUIRED',
            'publication':publication.key,'review_packet':str(packet.resolve())}]
        super().__init__('원문 표지의 공보번호·종별을 자동 식별할 수 없습니다. 원문 식별 검수 후 재개하세요: '+str(packet.resolve()))


def verify_original(publication, original, count, work, source, biblio_url, original_url):
    reader = inspect_pdf(original)
    if len(reader.pages) != count:
        raise CollectionError('원문 전체 페이지 수 불일치')
    try:
        text = reader.pages[0].extract_text() or ''
    except Exception:
        # Encoding failure is not identity evidence. Preserve the PDF for review.
        text = ''
    identifiers = extract(text)
    if identifiers:
        same = [p for p in identifiers if p.country==publication.country and p.number==publication.number]
        exact = any(p.kind==publication.kind for p in same)
        if exact and all(p.country==publication.country and p.number==publication.number
                         and p.kind==publication.kind for p in identifiers):
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
