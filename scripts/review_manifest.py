"""Create a review form, never auto-approve its contents."""
import argparse
import json
from pathlib import Path
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'scripts'
from .input_parser import one
from .pdf_merger import sha256


def main():
    p = argparse.ArgumentParser(description='검토용 manifest 생성 (모든 확인 항목은 false)')
    p.add_argument('--input-number', required=True)
    p.add_argument('--publication', required=True)
    p.add_argument('--biblio', type=Path, required=True)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--source', choices=['Espacenet', 'KIPRIS'], required=True)
    p.add_argument('--biblio-url', required=True)
    p.add_argument('--original-url', required=True)
    p.add_argument('--original-pages', type=int, required=True, help='공식 사이트 뷰어에서 확인한 총 페이지')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    item = dict(publication=one(a.publication).key, source=a.source,
        biblio_pdf=str(a.biblio.resolve()), original_pdf=str(a.original.resolve()),
        biblio_url=a.biblio_url, original_url=a.original_url, original_pages=a.original_pages,
        biblio_sha256=sha256(a.biblio), original_sha256=sha256(a.original),
        identity_verified=False, english_abstract_verified=False, full_document_verified=False,
        layout_verified=False, verification_note='')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8') as f:
        json.dump({one(a.input_number).key: item}, f, ensure_ascii=False, indent=2)
    print('검토 양식 생성. 실제 검토 후 해당 플래그와 근거를 작성하세요: ' + str(a.out))


if __name__ == '__main__':
    main()
