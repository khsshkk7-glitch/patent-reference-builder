import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfWriter
from scripts.ops_client import OpsClient, full_image, configured
from scripts.input_parser import one
from scripts.browser_session import CollectionError
from scripts.pdf_merger import inspect_pdf

XML = b'''<world xmlns:ops="http://ops.epo.org"><ops:document-instance link="JP/3102826/U/fullimage" number-of-pages="2" desc="FullDocument"><ops:document-format>application/pdf</ops:document-format></ops:document-instance></world>'''


class FastClient(OpsClient):
    def get(self,*args):
        self.next_request=0
        return super().get(*args)


class OpsTests(unittest.TestCase):
    def test_received_scan_pending_identity_is_not_download_failure(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from scripts.espacenet_collector import download_original
        from scripts.original_identity import IdentityReviewRequired, DocumentIdentityMismatch
        pub = one('JP2006198019A')
        page = MagicMock()
        page.url = 'https://worldwide.espacenet.com/record'
        page.locator.return_value.inner_text.return_value = pub.key
        page.locator.return_value.text_content.return_value = '1 of 9'
        for error, status in ((IdentityReviewRequired(pub, Path('review.json')), 'identity_review_pending'),
                              (DocumentIdentityMismatch('wrong cover'), 'failed')):
            args = SimpleNamespace(original_method='ops', ops_client=MagicMock())
            args.ops_client.download.return_value = (Path('original.pdf'),9,'https://ops.epo.org/images')
            with patch('scripts.espacenet_collector.verify_original',side_effect=error):
                with self.assertRaises(type(error)):
                    download_original(page,pub,Path('.'),args)
            metrics = args.download_metrics[pub.key]
            self.assertEqual(metrics['status'],status)
            self.assertEqual(metrics['captcha_prompts'],0)
            if status == 'identity_review_pending': self.assertEqual(metrics['pages'],9)
            args.ops_client.download.assert_called_once()

    def test_explicit_ops_without_key_stops_before_browser(self):
        from scripts.build_references import parser, run
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'EPO_OPS_KEY':'','EPO_OPS_SECRET':''}), \
            patch('scripts.build_references.browser_session',side_effect=AssertionError('No browser without key')):
            args=parser().parse_args(['--text','JP3102826U','--original-method','ops','--out',tmp])
            with self.assertRaisesRegex(ValueError,'키 미설정'):run(args)

    def test_local_prompt_restores_environment(self):
        from scripts.run_with_ops import main
        def checked(args):
            import os
            self.assertEqual(args.original_method,'ops')
            self.assertEqual(os.environ['EPO_OPS_KEY'],'unit-key')
            self.assertEqual(os.environ['EPO_OPS_SECRET'],'unit-secret')
            return 0
        with patch.dict('os.environ',{'EPO_OPS_KEY':'','EPO_OPS_SECRET':''}), \
            patch('sys.argv',['run_with_ops.py','--text','JP3102826U']), \
            patch('scripts.run_with_ops.getpass',side_effect=['unit-key','unit-secret']), \
            patch('scripts.run_with_ops.run',side_effect=checked):
            self.assertEqual(main(),0)
            import os
            self.assertEqual(os.environ['EPO_OPS_KEY'],'')
            self.assertEqual(os.environ['EPO_OPS_SECRET'],'')

    def test_missing_key_has_no_network(self):
        with patch.dict('os.environ',{'EPO_OPS_KEY':'','EPO_OPS_SECRET':''}):
            self.assertFalse(configured())
            def forbidden(*args,**kwargs): self.fail('No request without configured credentials')
            with self.assertRaisesRegex(CollectionError,'키 미설정'):
                OpsClient(transport=forbidden).download(one('JP3102826U'),'.')

    def test_exact_kind_full_document_and_page_count(self):
        pub=one('JP3102826U')
        self.assertEqual(full_image(XML,pub),('JP/3102826/U/fullimage',2))
        for xml in (XML.replace(b'/U/',b'/B/'), XML.replace(b'FullDocument',b'FirstPageClipping'),
                    XML.replace(b'number-of-pages="2"',b'number-of-pages="0"'), XML.replace(b'/3102826/',b'/3102827/')):
            with self.assertRaises(CollectionError):full_image(xml,pub)

    def test_all_pages_in_order_no_browser_or_challenge(self):
        calls=[]
        def transport(url,headers,data=None,timeout=None):
            calls.append(url)
            if '/auth/' in url:
                return json.dumps(dict(access_token='test-token',expires_in='1199')).encode()
            if url.endswith('/images'):return XML
            writer=PdfWriter();writer.add_blank_page(width=500+int(url[-1]),height=700)
            stream=io.BytesIO();writer.write(stream);writer.close();return stream.getvalue()
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'EPO_OPS_KEY':'test-key','EPO_OPS_SECRET':'test-secret'}):
            client=FastClient(transport=transport)
            path,count,url=client.download(one('JP3102826U'),tmp,expected_pages=2)
            result=inspect_pdf(path)
            self.assertEqual(count,2)
            self.assertEqual([int(p.mediabox.width) for p in result.pages],[501,502])
            self.assertEqual(sum('/auth/' in u for u in calls),1)
            evidence=Path(tmp,'ops-download.json').read_text(encoding='utf-8')
            self.assertNotIn('test-token',evidence);self.assertNotIn('test-secret',evidence)
            self.assertEqual(json.loads(evidence)['captcha_prompts'],0)

    def test_viewer_mismatch_stops_before_page_download(self):
        calls=[]
        def transport(url,headers,data=None,timeout=None):
            calls.append(url)
            return json.dumps(dict(access_token='test-token',expires_in='1199')).encode() if '/auth/' in url else XML
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'EPO_OPS_KEY':'test-key','EPO_OPS_SECRET':'test-secret'}):
            with self.assertRaisesRegex(CollectionError,'페이지 불일치'):
                FastClient(transport=transport).download(one('JP3102826U'),tmp,expected_pages=3)
            self.assertFalse(any('Range=' in u for u in calls))

    def test_html_instead_of_pdf_never_becomes_complete(self):
        def transport(url,headers,data=None,timeout=None):
            if '/auth/' in url:return b'{"access_token":"test","expires_in":"1199"}'
            return XML if url.endswith('/images') else b'<html>error</html>'
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'EPO_OPS_KEY':'test-key','EPO_OPS_SECRET':'test-secret'}):
            with self.assertRaisesRegex(CollectionError,'PDF가 아닙니다'):
                FastClient(transport=transport).download(one('JP3102826U'),tmp)
            self.assertFalse(Path(tmp,'original-ops.pdf').exists())
