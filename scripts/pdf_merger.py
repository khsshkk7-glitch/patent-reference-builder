"""Keep every original page; validate counts and publish atomically."""
from pathlib import Path
from contextlib import contextmanager
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


@contextmanager
def staged_pdf(output):
    """Keep incomplete bytes under a private temporary name in the destination folder."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".reference-", suffix=".pdf.part", dir=output.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


def publish_pdf(tmp, output):
    """Atomically add a final name without replacing an existing file.

    Both paths are on the same filesystem. Unsupported hard links fail explicitly;
    never fall back to a partial copy or an overwriting rename.
    """
    os.link(tmp, output)


def copy_original_unique(original, output, expected_pages):
    """Keep a separately labelled original-only file byte-for-byte unchanged."""
    reader = inspect_pdf(original)
    if len(reader.pages) != expected_pages or expected_pages < 1:
        raise ValueError('원문 페이지 수 불일치')
    output = Path(output)
    data = Path(original).read_bytes()
    with staged_pdf(output) as tmp:
        with tmp.open('wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if len(inspect_pdf(tmp).pages) != expected_pages:
            raise ValueError('저장된 원문 페이지 수 불일치')
        digest = sha256(tmp)
        if digest != hashlib.sha256(data).hexdigest():
            raise ValueError('저장된 원문 바이트 불일치')
        stats = dict(pages=expected_pages, biblio_pages=0,
                     original_pages=expected_pages, sha256=digest)
        number = 1
        while True:
            candidate = output if number == 1 else output.with_name(f'{output.stem} ({number}){output.suffix}')
            try:
                publish_pdf(tmp, candidate)
                return candidate, stats
            except FileExistsError:
                number += 1


def merge(biblio, original, output, expected_original_pages):
    b, o = inspect_pdf(biblio), inspect_pdf(original)
    if len(o.pages) != expected_original_pages or expected_original_pages < 1:
        raise ValueError(f"원문 페이지 수 불일치: {len(o.pages)} / {expected_original_pages}")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"기존 결과를 덮어쓰지 않습니다: {output.name}")
    with staged_pdf(output) as tmp:
        writer = PdfWriter()
        try:
            writer.append(b)
            writer.append(o)
            writer.add_metadata({"/Title": output.stem, "/Subject": "English bibliographic data and abstract; original publication"})
            with tmp.open('wb') as handle:
                writer.write(handle)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            writer.close()
        actual = len(inspect_pdf(tmp).pages)
        if actual != len(b.pages) + len(o.pages):
            raise ValueError("병합 페이지 수 불일치")
        stats = {"pages": actual, "biblio_pages": len(b.pages), "original_pages": len(o.pages), "sha256": sha256(tmp)}
        publish_pdf(tmp, output)
        return stats


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
