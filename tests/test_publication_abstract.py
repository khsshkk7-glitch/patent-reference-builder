"""A registered original may use a disclosed KPA abstract from the same application."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from pypdf import PdfReader
from scripts.browser_session import CollectionError
from scripts.collector_common import Collected
from scripts.input_parser import one
from scripts.kipris_collector import (publication_mapping,
    collect_domestic_for_translation, TranslationRequired)
from tests.test_kipris_domestic import fixture_pdf
from tests.test_kpa_fallback import kpa_html, ABSTRACT


class PublicationMapping(TestCase):
    def test_registration_maps_to_exact_laid_open_number(self):
        pub, app = publication_mapping(one('KR102200733B1'),
            '출원번호(일자) 1020190067956 (2019.06.10)',
            '공개번호(일자) 1020200141229 (2020.12.18)')
        self.assertEqual((pub.key, app), ('KR20200141229A', '1020190067956'))

    def test_utility_keeps_20_and_u(self):
        pub, app = publication_mapping(one('KR200355113Y1'),
            '20-2004-0008221', '20-2004-0032123')
        self.assertEqual((pub.key, app), ('KR20040032123U', '2020040008221'))

    def test_unpublished_or_already_laid_open_does_not_invent_mapping(self):
        self.assertIsNone(publication_mapping(one('KR102200733B1'), '1020190067956', ''))
        self.assertIsNone(publication_mapping(one('KR20200141229A'), '', '1020200141229'))

    def test_wrong_right_and_ambiguous_numbers_are_rejected(self):
        for app, pub in [('2020190067956', '1020200141229'),
                         ('1020190067956', '2020200141229'),
                         ('1020190067956 1020190000001', '1020200141229')]:
            with self.subTest(app=app, pub=pub), self.assertRaises(CollectionError):
                publication_mapping(one('KR102200733B1'), app, pub)


DOMESTIC = '''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">국내</a></div>
<input id="queryText"><button>검색</button><section id="resultSection">
<article><button>[1] fixture</button></article></section>
<div id="mainResultDetail"><button>상세정보</button><table>
<tr><th scope="row">등록번호(일자)</th><td>1022007330000</td></tr>
<tr><th scope="row">출원번호(일자)</th><td>1020190067956 (2019.06.10)</td></tr>
<tr><th scope="row">공개번호(일자)</th><td>1020200141229 (2020.12.18)</td></tr>
</table><div id="sum_all">요약 한국어 초록</div></div>'''


class PublicationAbstractBrowser(TestCase):
    def exercise(self, *, wrong_app=False, missing=False):
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
            browser = pw.chromium.launch()
            try:
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(3000)
                child_html = kpa_html(['1020200141229 A'], detail='1020200141229 A')
                child_html = child_html.replace('2020040008221',
                    '1020190000001' if wrong_app else '1020190067956')
                if missing:
                    child_html = '''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">KPA</a></div>
                    <input id="queryText"><button>검색</button><section id="resultSection">
                    <div class="nodata-area">검색결과가 없습니다</div></section>'''
                def route(r):
                    body = (ABSTRACT if r.request.url.endswith('/print') else
                            DOMESTIC if r.request.frame.page == page else child_html)
                    r.fulfill(body=body, content_type='text/html; charset=utf-8')
                context.route('**/*', route)
                work = Path(tmp)
                original = work / 'original.pdf'
                original.write_bytes(fixture_pdf('10-2200733'))
                requested = one('KR102200733B1')
                parts = Collected(requested, None, original, 2, 'KIPRIS',
                    'https://www.kipris.or.kr/', 'https://www.kipris.or.kr/', 'registered original')
                args = SimpleNamespace(retries=1, selectors={})
                with patch('scripts.kipris_collector.download_domestic_pane', return_value=parts) as download:
                    if wrong_app:
                        with self.assertRaisesRegex(CollectionError, '출원번호.*다릅니다'):
                            collect_domestic_for_translation(page, requested, work, args)
                        download.assert_not_called()
                    elif missing:
                        with self.assertRaises(TranslationRequired):
                            collect_domestic_for_translation(page, requested, work, args)
                        record = json.loads((work / 'publication-abstract-mapping.json').read_text(encoding='utf-8'))
                        self.assertEqual(record['status'], 'no_exact_kpa')
                        self.assertTrue((work / 'translation-review.json').exists())
                        download.assert_called_once()
                    else:
                        result = collect_domestic_for_translation(page, requested, work, args)
                        self.assertEqual(result.publication.key, 'KR102200733B1')
                        self.assertEqual(result.original, original)
                        self.assertEqual(result.translation_type, 'official')
                        prov = result.biblio_provenance
                        self.assertEqual(prov['abstract_publication'], 'KR20200141229A')
                        self.assertEqual(prov['application'], '1020190067956')
                        self.assertTrue(prov['mapping_verified'])
                        text = ''.join(p.extract_text() or '' for p in PdfReader(result.biblio).pages)
                        self.assertIn(ABSTRACT, text)
                        self.assertIn('Requested original: KR102200733B1', text)
                        self.assertIn('KR20200141229A', text)
                        self.assertFalse((work / 'translation-review.json').exists())
                        download.assert_called_once()
                        self.assertEqual(download.call_args.args[1].key, 'KR102200733B1')
                    self.assertEqual(len(context.pages), 1)
            finally:
                browser.close()

    def test_publication_abstract_keeps_registered_original_and_printed_notice(self):
        self.exercise()

    def test_same_publication_digits_with_different_application_are_rejected(self):
        self.exercise(wrong_app=True)

    def test_missing_publication_kpa_only_then_allows_translation(self):
        self.exercise(missing=True)
