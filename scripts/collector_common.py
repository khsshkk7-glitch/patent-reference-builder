"""Print the source document pane, retain evidence, validate both parts."""
from dataclasses import dataclass
from pathlib import Path
import re
from .input_parser import extract, resolve
from .pdf_merger import inspect_pdf, sha256
from .browser_session import CollectionError, assert_official_url


def trim_blank_print_tail(path):
    """Remove only provably empty/white rectangle overflow in printed bibliography.

    Unknown drawing operators, text, images and annotations are retained.
    Never apply this to an official original publication.
    """
    from pypdf import PdfWriter
    from pypdf.generic import ContentStream
    def blank(page, reader):
        if page.get('/Annots'):
            return False
        stream = page.get_contents()
        if stream is None:
            return True
        white, stack = False, []
        for operands, op in ContentStream(stream, reader).operations:
            if op == b'q':
                stack.append(white)
            elif op == b'Q':
                if not stack:
                    return False
                white = stack.pop()
            elif op in (b'rg', b'g'):
                white = all(float(x) == 1 for x in operands)
            elif op in (b'RG', b'G'):
                pass  # Stroke colour does not paint; stroke operators are rejected.
            elif op == b'f':
                if not white:
                    return False
            elif op not in (b'cm', b'gs', b're'):
                return False
        return not stack
    reader = inspect_pdf(path)
    keep = len(reader.pages)
    while keep > 1 and blank(reader.pages[keep-1], reader):
        keep -= 1
    if keep == len(reader.pages):
        return 0
    writer = PdfWriter()
    writer.append(reader, pages=(0, keep))
    if reader.metadata:
        writer.add_metadata(dict(reader.metadata))
    # Build bytes before replacing the generated print file.
    import io
    buffer = io.BytesIO()
    writer.write(buffer)
    writer.close()
    Path(path).write_bytes(buffer.getvalue())
    return len(reader.pages)-keep


@dataclass
class Collected:
    publication: object
    biblio: Path | None
    original: Path
    original_pages: int
    source: str
    biblio_url: str
    original_url: str
    verification: str
    missing_fields: tuple = ()
    translation_type: str = 'official'
    ai_provenance: dict | None = None
    biblio_provenance: dict | None = None


def english_abstract(text):
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    if len(text.strip()) < 50:
        raise CollectionError("영문 초록이 없거나 너무 짧아 자동 검증할 수 없습니다.")
    if detect(text) != "en":
        raise CollectionError("영문 초록으로 확인되지 않았습니다.")


def print_biblio(page, container, abstract, path, hide=(), scale=1):
    """Print original DOM with print CSS; never regenerate or translate its content."""
    english_abstract(abstract)
    root = page.locator(container)
    if root.count() != 1:
        raise CollectionError("인쇄 영역이 단일하지 않습니다.")
    # Hide siblings along the ancestor path; leave all original data inside the pane.
    root.evaluate("""el => {
      el.setAttribute('data-reference-print-root','true');
      let n=el; while(n.parentElement){
        for(const sibling of n.parentElement.children){if(sibling!==n) sibling.setAttribute('data-reference-hide','true');}
        n=n.parentElement; n.setAttribute('data-reference-print-ancestor','true');
      }
    }""")
    css = """@page {size:A4; margin:14mm;}
    @media print {
      [data-reference-hide], .noPrint, .epoToolBar, #languageSelectorContainer {display:none!important;}
      html,body {width:auto!important; min-width:0!important; height:auto!important; overflow:visible!important;}
      [data-reference-print-ancestor] {display:block!important;position:static!important;width:100%!important;height:auto!important;min-width:0!important;max-height:none!important;overflow:visible!important;margin:0!important;padding:0!important;float:none!important;flex:none!important;}
      [data-reference-print-root], [data-reference-print-root] * {max-width:100%!important; overflow:visible!important;}
      [data-reference-print-root] {margin:0!important; padding:0!important; width:100%!important; float:none!important; position:static!important; font:10pt Arial,sans-serif;}
      table {width:100%!important; table-layout:auto!important;} th,td{overflow-wrap:anywhere;}
      #pagebody table th {width:32mm!important;min-width:32mm!important;word-break:normal!important;overflow-wrap:normal!important;vertical-align:top;}
      #pagebody .hidden, #pagebody a[onclick*="secondary"] {display:none!important;}
      img {max-width:100%!important; height:auto!important;} a{color:#111!important;text-decoration:none!important;}
    }"""
    if hide:
        css += "@media print {" + ",".join(hide) + "{display:none!important;}}"
    style = page.add_style_tag(content=css)
    try:
        page.evaluate("document.fonts.ready")
        page.wait_for_function("""() => [...document.querySelectorAll('[data-reference-print-root] img')].every(i=>i.complete && i.naturalWidth>0)""")
        page.pdf(path=str(path), format="A4", print_background=True, prefer_css_page_size=True,
                 display_header_footer=False, scale=scale)
        trim_blank_print_tail(path)
        reader = inspect_pdf(path)
        printed = " ".join(p.extract_text() or "" for p in reader.pages)
        # Detect accidental clipping/missing abstract, independent of page count.
        normalize = lambda s: re.sub(r"\s+", "", s)
        if normalize(abstract) not in normalize(printed):
            raise CollectionError("인쇄 PDF에 영문 초록 전체가 보존되지 않았습니다.")
        for p in reader.pages:
            if abs(float(p.mediabox.width)-595.28) > 2 or abs(float(p.mediabox.height)-841.89) > 2:
                raise CollectionError("서지 PDF가 A4 규격이 아닙니다.")
    finally:
        style.evaluate("el=>el.remove()")
        page.evaluate("""() => document.querySelectorAll('[data-reference-hide],[data-reference-print-root],[data-reference-print-ancestor]').forEach(e=>{e.removeAttribute('data-reference-hide');e.removeAttribute('data-reference-print-root');e.removeAttribute('data-reference-print-ancestor')})""")


def from_manifest(requested, entry, base):
    """Explicit reviewed resume path for inaccessible/changed sites and scanned PDFs."""
    from .input_parser import one
    publication = one(entry["publication"])
    if not publication.kind:
        raise CollectionError('검토 manifest의 publication에는 확정된 문헌 종류 코드가 필요합니다.')
    if requested.role == "application":
        if entry.get("application") != requested.key:
            raise CollectionError("출원번호-공보번호 매핑 증거가 없습니다.")
        if not entry.get("mapping_verified"):
            raise CollectionError("출원번호 매핑 검토 필요")
        if requested.country != publication.country:
            raise CollectionError("출원/공보 국가 불일치")
    else:
        resolve(requested, [publication])
    source = entry["source"]
    if source not in ("Espacenet", "KIPRIS", "KIPRIS + Espacenet", 'Espacenet + EPO OPS'):
        raise CollectionError("지원 출처는 Espacenet/KIPRIS입니다.")
    if source in ("KIPRIS", "KIPRIS + Espacenet") and publication.country != "KR":
        raise CollectionError("KIPRIS 보조 수집은 KR만 지원합니다.")
    biblio_source = 'Espacenet' if source in ('Espacenet','Espacenet + EPO OPS') else 'KIPRIS'
    original_source = 'KIPRIS' if source == 'KIPRIS' else 'Espacenet'
    assert_official_url(entry["biblio_url"], biblio_source)
    assert_official_url(entry["original_url"], original_source)
    for key in ("identity_verified", "english_abstract_verified", "full_document_verified", "layout_verified"):
        if entry.get(key) is not True:
            raise CollectionError("검토 기록 누락: " + key)
    if not str(entry.get("verification_note", "")).strip():
        raise CollectionError("검토 근거(첫 페이지 번호·마지막 페이지·도면 등)를 기록하세요.")
    b, o = (Path(base) / entry[k] for k in ("biblio_pdf", "original_pdf"))
    for key, path in (("biblio_sha256", b), ("original_sha256", o)):
        if entry.get(key) != sha256(path):
            raise CollectionError("검토 후 파일 변경 또는 SHA-256 누락: " + key)
    br, orig = inspect_pdf(b), inspect_pdf(o)
    for p in br.pages:
        if abs(float(p.mediabox.width)-595.28)>2 or abs(float(p.mediabox.height)-841.89)>2:
            raise CollectionError("서지 PDF는 A4여야 합니다.")
    count = entry["original_pages"]
    if type(count) is not int or len(orig.pages) != count:
        raise CollectionError("검토된 원문 총 페이지 수 불일치")
    provenance = entry.get('biblio_provenance')
    if provenance is not None:
        from .input_parser import one, korean_right
        if not isinstance(provenance, dict):
            raise CollectionError('공개공보 초록 출처 기록 형식 오류')
        abstract_pub = one(provenance['abstract_publication'])
        right = korean_right(publication)
        if (provenance.get('requested_publication') != publication.key
                or provenance.get('mapping_verified') is not True
                or publication.country != 'KR' or not publication.kind.startswith(('B', 'Y'))
                or abstract_pub.country != 'KR' or korean_right(abstract_pub) != right
                or abstract_pub.kind != ('U' if right == '20' else 'A')
                or not re.fullmatch(right + r'\d{11}', provenance.get('application', ''))
                or not provenance.get('source_notice')):
            raise CollectionError('등록공보·공개공보·동일 출원 매핑 검토 기록 불일치')
        printed = ''.join(p.extract_text() or '' for p in br.pages)
        compact = lambda value: re.sub(r'\s+', '', value)
        if compact(provenance['source_notice']) not in compact(printed):
            raise CollectionError('공개공보 초록의 앞장 출처 고지 누락')
    return Collected(publication, b, o, count, source, entry["biblio_url"], entry["original_url"],
                     entry["verification_note"], biblio_provenance=provenance)
