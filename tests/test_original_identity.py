import json
import tempfile
import zipfile
from pathlib import Path
from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import patch
from scripts.input_parser import one
from scripts.original_identity import verify_original,IdentityReviewRequired,DocumentIdentityMismatch
from scripts.build_references import run,parser,collect
from tests.test_kipris_domestic import fixture_pdf


class OriginalIdentity(TestCase):
    def test_blank_cover_or_matching_number_without_kind_stays_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);pdf=work/'original.pdf';pub=one('JP2006198019A')
            for text in ('', 'JP2006198019'):
                pdf.write_bytes(fixture_pdf(text))
                with self.assertRaises(IdentityReviewRequired):
                    verify_original(pub,pdf,2,work,'Espacenet','https://worldwide.espacenet.com/biblio','https://worldwide.espacenet.com/original')

    def test_rejects_wrong_cover_and_does_not_confuse_citations_with_cover_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);pdf=work/'original.pdf';pub=one('JP2006198019A')
            for text in ('JP2004121879A','US20200123456A1','JP2006198019B'):
                pdf.write_bytes(fixture_pdf(text))
                with self.assertRaises(DocumentIdentityMismatch):
                    verify_original(pub,pdf,2,work,'Espacenet','https://worldwide.espacenet.com/biblio','https://worldwide.espacenet.com/original')
            pdf.write_bytes(fixture_pdf('JP2006198019A cited US20200123456A1'))
            with self.assertRaises(IdentityReviewRequired):
                verify_original(pub,pdf,2,work,'Espacenet','https://worldwide.espacenet.com/biblio','https://worldwide.espacenet.com/original')
            pdf.write_bytes(fixture_pdf('US20200123456A1 cited JP2006198019A'))
            with self.assertRaises(IdentityReviewRequired):
                verify_original(pub,pdf,2,work,'Espacenet','https://worldwide.espacenet.com/biblio','https://worldwide.espacenet.com/original')

    def test_unidentifiable_original_preserved_and_never_merged_or_zipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pub=one('JP2006198019A')
            def unidentifiable(page,publication,work,args):
                original=work/'original.pdf';original.write_bytes(fixture_pdf('No readable publication identifier'))
                verify_original(pub,original,2,work,'Espacenet','https://worldwide.espacenet.com/biblio','https://worldwide.espacenet.com/original')
            args=parser().parse_args(['--text',pub.key,'--out',tmp,'--zip'])
            with patch('scripts.build_references.browser_session',return_value=nullcontext(object())),patch('scripts.build_references.collect',side_effect=unidentifiable):
                self.assertEqual(run(args),1)
            row=json.loads(next(root.glob('처리결과_*.json')).read_text(encoding='utf-8'))[0]
            self.assertEqual(row['status'],'원문 식별 검수 대기');self.assertFalse(row['complete_reference'])
            packet=Path(row['review_packet']);entry=json.loads(packet.read_text(encoding='utf-8'))[pub.key]
            self.assertTrue(Path(entry['original_pdf']).exists());self.assertFalse(entry['identity_verified'])
            self.assertFalse(list(root.glob('*.pdf')))
            with zipfile.ZipFile(next(root.glob('*.zip'))) as z:
                self.assertFalse(any(n.endswith('.pdf') for n in z.namelist()))

    def test_identity_failure_does_not_silently_fallback_to_kipris(self):
        for exc in (DocumentIdentityMismatch('wrong cover'),IdentityReviewRequired(one('KR20200137353A'),Path('review.json'))):
            with patch('scripts.build_references.espacenet_collector.collect',side_effect=exc),patch('scripts.build_references.kipris_collector.collect') as fallback:
                with self.assertRaises(type(exc)):
                    collect(None,one('KR20200137353A'),None,type('Args',(),{'source':'auto'})())
                fallback.assert_not_called()
