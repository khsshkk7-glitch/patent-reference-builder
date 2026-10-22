"""Unrelated KPA hits do not block exact domestic evidence or supply their abstract."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from scripts.browser_session import CollectionError
from scripts.collector_common import Collected
from scripts.input_parser import one
from scripts.kipris_collector import collect, TranslationRequired
from tests.test_kipris_domestic import fixture_pdf


ABSTRACT = 'An exact publication fixture includes a mounting structure and replaceable panels to support an article.'


def kpa_html(fields, detail='200355113 (Y1)'):
    articles = ''.join(f'<article><ul><li><span data-lang-id="srlt.kpa.pn">공고번호</span>{text}</li></ul>'
                       f'<button onclick="document.body.dataset.clicked=\'{i}\'">[{i+1}] fixture</button></article>'
                       for i, text in enumerate(fields))
    return f'''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">KPA</a></div>
      <input id="queryText"><button>검색</button><section id="resultSection">{articles}</section>
      <div id="mainResultDetail"><table><tr><th>공고번호(일자)</th><td>{detail}</td></tr>
      <tr><th>출원번호(일자)</th><td>2020040008221</td></tr></table><p class="txt">{ABSTRACT}</p>
      <a class="btn-print" onclick="window.open('/print')">인쇄</a></div>'''


class KpaFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.pw = sync_playwright().start(); self.addCleanup(self.pw.stop)
        self.browser = self.pw.chromium.launch(); self.addCleanup(self.browser.close)
        self.page = self.browser.new_page(); self.page.set_default_timeout(2000)
        self.args = SimpleNamespace(selectors={}, retries=1)
        self.pub = one('KR200355113Y1')

    def route(self, html):
        self.page.context.route('**/*', lambda r:r.fulfill(body=ABSTRACT if r.request.url.endswith('/print') else html,
                                                content_type='text/html; charset=utf-8'))

    def evidence(self):
        return json.loads((self.work / 'kpa-candidates.json').read_text(encoding='utf-8'))

    def test_unrelated_publications_even_with_requested_application_digits_fall_back(self):
        self.route(kpa_html(['101234567']) + '<div>출원번호 200355113; English abstract of another patent</div>')
        with patch('scripts.kipris_collector.collect_domestic_for_translation', return_value='domestic') as fallback, \
             patch('scripts.kipris_collector.print_biblio') as printer:
            self.assertEqual(collect(self.page, self.pub, self.work, self.args), 'domestic')
            fallback.assert_called_once_with(self.page, self.pub, self.work, self.args)
            printer.assert_not_called()
        self.assertEqual(self.evidence()['reason'], 'no_exact_publication')
        self.assertEqual(self.evidence()['candidates'][0]['state'], 'other_publication')

    def test_wrong_kind_only_falls_back_for_requested_kind(self):
        self.route(kpa_html(['200355113 (Y2)']))
        with patch('scripts.kipris_collector.collect_domestic_for_translation', return_value='domestic') as fallback:
            self.assertEqual(collect(self.page, self.pub, self.work, self.args), 'domestic')
            self.assertEqual(fallback.call_args.args[1].kind, 'Y1')
        self.assertEqual(self.evidence()['candidates'][0]['state'], 'wrong_kind')

    def test_wrong_detail_kind_does_not_supply_english_abstract(self):
        self.route(kpa_html(['200355113'], detail='200355113 (Y2)'))
        with patch('scripts.kipris_collector.collect_domestic_for_translation', return_value='domestic') as fallback, \
             patch('scripts.kipris_collector.print_biblio') as printer:
            self.assertEqual(collect(self.page, self.pub, self.work, self.args), 'domestic')
            fallback.assert_called_once(); printer.assert_not_called()
        self.assertEqual(self.evidence()['reason'], 'detail_wrong_kind')

    def test_ambiguous_exact_matches_stop_without_fallback(self):
        self.route(kpa_html(['200355113 (Y1)', '200355113 (Y1)']))
        with patch('scripts.kipris_collector.collect_domestic_for_translation') as fallback:
            with self.assertRaisesRegex(CollectionError, '단일하지'): collect(self.page, self.pub, self.work, self.args)
            fallback.assert_not_called()
        self.assertEqual(self.evidence()['reason'], 'ambiguous_candidates')

    def test_unreadable_field_is_not_misreported_as_missing_kpa(self):
        self.route(kpa_html(['unreadable']))
        with patch('scripts.kipris_collector.collect_domestic_for_translation') as fallback:
            with self.assertRaisesRegex(CollectionError, '읽을 수'): collect(self.page, self.pub, self.work, self.args)
            fallback.assert_not_called()
        self.assertEqual(self.evidence()['reason'], 'unreadable_publication_field')

    def test_missing_kind_still_requires_confirmation_before_domestic_lookup(self):
        self.route(kpa_html(['101234567']))
        with self.assertRaisesRegex(CollectionError, '종별을 먼저 확정'):
            collect(self.page, one('KR200355113'), self.work, self.args)
        self.assertFalse(list(self.work.glob('*.pdf')))

    def test_exact_match_preserves_official_kpa_route(self):
        self.route(kpa_html(['200355113 (Y1)']))
        with patch('scripts.kipris_collector.collect_domestic_for_translation') as fallback, \
             patch('scripts.kipris_collector.print_biblio') as printer, \
             patch('scripts.kipris_collector.collect_domestic', return_value='official') as domestic:
            self.assertEqual(collect(self.page, self.pub, self.work, self.args), 'official')
            fallback.assert_not_called(); printer.assert_called_once(); domestic.assert_called_once()
        self.assertEqual(self.evidence()['reason'], 'selected_candidate')

    def test_unrelated_kpa_to_exact_domestic_creates_unreviewed_translation_packet(self):
        # The first route is KPA. The second navigation is the actual domestic adapter.
        domestic_html = '''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">국내</a></div>
          <input id="queryText"><button>검색</button><section id="resultSection"><article><button>[1] domestic</button></article></section>
          <div id="mainResultDetail"><button>상세정보</button><table><tr><th scope="row">등록번호(일자)</th><td>2003551130000</td></tr></table>
          <div id="sum_all">요약 국내 동일 공보의 한국어 초록</div></div>'''
        calls = []
        def route(r):
            calls.append(r.request.url)
            r.fulfill(body=kpa_html(['101234567']) if len(calls) == 1 else domestic_html,
                      content_type='text/html; charset=utf-8')
        self.page.route('**/*', route)
        original = self.work / 'original.pdf'; original.write_bytes(fixture_pdf('20-0355113'))
        parts = Collected(self.pub, None, original, 2, 'KIPRIS', 'https://www.kipris.or.kr/', 'https://www.kipris.or.kr/', '')
        with patch('scripts.kipris_collector.download_domestic_pane', return_value=parts) as download, \
             patch('scripts.kipris_collector.print_biblio') as printer:
            with self.assertRaises(TranslationRequired): collect(self.page, self.pub, self.work, self.args)
            self.assertEqual(download.call_args.args[1].key, self.pub.key)
            printer.assert_not_called()
        entry = json.loads((self.work / 'translation-review.json').read_text(encoding='utf-8'))[self.pub.key]
        self.assertIn('국내 동일 공보', entry['source_text'])
        self.assertEqual(entry['english_abstract'], '')
        self.assertFalse(entry['translation_reviewed']); self.assertFalse(entry['identity_verified'])
        self.assertEqual(original.read_bytes(), fixture_pdf('20-0355113'))
        self.assertEqual(self.evidence()['reason'], 'no_exact_publication')


if __name__ == '__main__': unittest.main()
