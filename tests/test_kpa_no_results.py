from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from scripts.kipris_collector import collect
from scripts.browser_session import CollectionError
from scripts.input_parser import one


class KpaNoResults(TestCase):
    def test_absent_exact_kpa_is_a_data_result_not_a_locator_timeout(self):
        html='''<div id="patentTabPannel"><a href="#">KPA</a></div><input id="queryText">
        <button onclick="document.querySelector('#resultSection').innerHTML='<div class=nodata-area>200355113 검색결과가 없습니다.</div>'">검색</button>
        <div id="resultSection"></div>'''
        with sync_playwright() as pw, TemporaryDirectory() as tmp:
            browser=pw.chromium.launch();page=browser.new_page();page.set_default_timeout(3000)
            page.route('**/*',lambda route:route.fulfill(body=html,content_type='text/html; charset=utf-8'))
            args=SimpleNamespace(selectors={},retries=1)
            # Absence of English KPA must route to domestic evidence collection.
            with patch('scripts.kipris_collector.collect_domestic_for_translation', return_value='domestic-review') as fallback:
                self.assertEqual(collect(page,one('KR200355113Y1'),Path(tmp),args), 'domestic-review')
                fallback.assert_called_once()
            self.assertFalse(list(Path(tmp).glob('*.pdf')))
            browser.close()
