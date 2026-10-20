"""Keep every original page; validate counts and publish atomically."""
from pathlib import Path
import hashlib
import os
import tempfile
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


def copy_original_unique(original, output, expected_pages):
    """Keep a separately labelled original-only file byte-for-byte unchanged."""
    reader = inspect_pdf(original)
    if len(reader.pages) != expected_pages or expected_pages < 1:
        raise ValueError('원문 페이지 수 불일치')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = Path(original).read_bytes()
    number = 1
    while True:
        candidate = output if number == 1 else output.with_name(f'{output.stem} ({number}){output.suffix}')
        try:
            with candidate.open('xb') as handle:
                handle.write(data)
            return candidate, dict(pages=expected_pages, biblio_pages=0,
                original_pages=expected_pages, sha256=sha256(candidate))
        except FileExistsError:
            number += 1


def merge(biblio, original, output, expected_original_pages):
    b, o = inspect_pdf(biblio), inspect_pdf(original)
    if len(o.pages) != expected_original_pages or expected_original_pages < 1:
        raise ValueError(f"원문 페이지 수 불일치: {len(o.pages)} / {expected_original_pages}")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"기존 결과를 덮어쓰지 않습니다: {output.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".reference-", suffix=".pdf.part", dir=output.parent)
    os.close(fd)
    tmp = Path(name)
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


def merge_unique(biblio, original, output, expected_original_pages):
    """Keep existing files; record the actual numbered filename on collision."""
    output = Path(output)
    number = 1
    while True:
        candidate = output if number == 1 else output.with_name(f"{output.stem} ({number}){output.suffix}")
        try:
            return candidate, merge(biblio, original, candidate, expected_original_pages)
        except FileExistsError:
            if not candidate.exists():
                raise
            number += 1
