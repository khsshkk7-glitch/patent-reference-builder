from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from scripts.kipris_collector import recover_original
from scripts.input_parser import one
from scripts.collector_common import from_manifest
from scripts.pdf_merger import sha256
from scripts.browser_session import CollectionError
from pypdf import PdfWriter


class Recovery(TestCase):
    def test_mixed_source_manifest_checks_each_official_origin(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('b.pdf','o.pdf'):
                writer=PdfWriter();writer.add_blank_page(width=595.28,height=841.89)
                writer.write(root/name);writer.close()
            item=dict(publication='KR20200137353A',source='KIPRIS + Espacenet',
                biblio_pdf='b.pdf',original_pdf='o.pdf',original_pages=1,
                biblio_url='https://www.kipris.or.kr/khome/search/searchResult.do',
                original_url='https://worldwide.espacenet.com/publicationDetails/originalDocument',
                biblio_sha256=sha256(root/'b.pdf'),original_sha256=sha256(root/'o.pdf'),
                identity_verified=True,english_abstract_verified=True,full_document_verified=True,
                layout_verified=True,verification_note='Synthetic fixture only')
            result=from_manifest(one('KR20200137353A'),item,root)
            self.assertEqual(result.source,'KIPRIS + Espacenet')
            item['original_url']='https://example.test/document.pdf'
            with self.assertRaises(CollectionError):from_manifest(one('KR20200137353A'),item,root)

    def test_preserves_kpa_bibliography_and_records_both_sources(self):
        with TemporaryDirectory() as tmp:
            work=Path(tmp)
            biblio=work/'biblio.pdf'
            biblio.write_bytes(b'original KPA fixture')
            publication=one('KR1020200137353A')
            original=work/'official.pdf'
            with patch('scripts.espacenet_collector.collect_original',return_value=(
                publication,original,19,'https://worldwide.espacenet.com/publicationDetails/originalDocument')) as collect:
                result=recover_original(None,publication,biblio,'https://www.kipris.or.kr/khome/search/searchResult.do',work,SimpleNamespace())
            self.assertEqual(result.biblio,biblio)
            self.assertEqual(biblio.read_bytes(),b'original KPA fixture')
            self.assertEqual(result.source,'KIPRIS + Espacenet')
            self.assertEqual(result.original_pages,19)
            self.assertEqual(collect.call_args.args[1],publication)

    def test_different_kind_is_not_accepted_as_recovery(self):
        with TemporaryDirectory() as tmp:
            with patch('scripts.espacenet_collector.collect_original',return_value=(
                one('KR1020200137353B1'),Path(tmp)/'wrong.pdf',19,'https://worldwide.espacenet.com/x')):
                with self.assertRaises(ValueError):
                    recover_original(None,one('KR1020200137353A'),Path(tmp)/'b.pdf','https://www.kipris.or.kr/x',Path(tmp),SimpleNamespace())
