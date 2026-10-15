"""Keep every original page; validate counts and publish atomically."""
from pathlib import Path
import hashlib
from pypdf import PdfReader, PdfWriter


def inspect_pdf(path):
    path = Path(path)
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"PDF가 아닌 응답: {path.name}")
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("암호화된 PDF는 처리하지 않습니다.")
    if not reader.pages:
        raise ValueError("빈 PDF")
    for page in reader.pages:
        if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
            raise ValueError("잘못된 페이지 크기")
    return reader


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def merge(biblio, original, output, expected_original_pages):
    b, o = inspect_pdf(biblio), inspect_pdf(original)
    if len(o.pages) != expected_original_pages or expected_original_pages < 1:
        raise ValueError(f"원문 페이지 수 불일치: {len(o.pages)} / {expected_original_pages}")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"기존 결과를 덮어쓰지 않습니다: {output.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".pdf.part")
    writer = PdfWriter()
    try:
        writer.append(b)
        writer.append(o)
        writer.add_metadata({"/Title": output.stem, "/Subject": "English bibliographic data and abstract; original publication"})
        writer.write(tmp)
        actual = len(inspect_pdf(tmp).pages)
        if actual != len(b.pages) + len(o.pages):
            raise ValueError("병합 페이지 수 불일치")
        # Exclusive create avoids overwriting another process's completed result.
        with output.open("xb") as out:
            out.write(tmp.read_bytes())
        return {"pages": actual, "biblio_pages": len(b.pages), "original_pages": len(o.pages), "sha256": sha256(output)}
    finally:
        writer.close()
        tmp.unlink(missing_ok=True)
