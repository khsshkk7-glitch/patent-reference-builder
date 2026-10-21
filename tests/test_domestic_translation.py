import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from scripts.kipris_collector import collect_domestic_for_translation, TranslationRequired
from scripts.collector_common import Collected
from scripts.input_parser import one
from scripts.ai_fallback import validate_packet
from scripts.browser_session import CollectionError
from scripts.build_references import run, parser
from tests.test_kipris_domestic import fixture_pdf


class DomesticTranslation(TestCase):
    def test_stages_korean_source_and_original_without_claiming_review(self):
        html='''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">국내</a></div>
        <input id="queryText"><button>검색</button><section id="resultSection">
        <article><button>[1] fixture</button></article></section>
        <div id="mainResultDetail"><button>상세정보</button><table><tr>
        <th scope="row">등록번호(일자)</th><td>2003551130000</td></tr></table>
        <div id="sum_all">요약 한국어 원문 초록은 번역 검토 전 그대로 보존한다.</div></div>'''
        pub=one('KR200355113Y1')
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
            browser=pw.chromium.launch(); page=browser.new_page();page.set_default_timeout(2000)
            page.route('**/*',lambda r:r.fulfill(body=html,content_type='text/html; charset=utf-8'))
            work=Path(tmp); original=work/'original.pdf';original.write_bytes(fixture_pdf('20-0355113'))
            parts=Collected(pub,None,original,2,'KIPRIS','https://www.kipris.or.kr/','https://www.kipris.or.kr/','')
            with patch('scripts.kipris_collector.download_domestic_pane',return_value=parts):
                with self.assertRaises(TranslationRequired):
                    collect_domestic_for_translation(page,pub,work,SimpleNamespace(retries=1))
            entry=json.loads((work/'translation-review.json').read_text(encoding='utf-8'))[pub.key]
            self.assertIn('한국어 원문 초록',entry['source_text'])
            self.assertFalse(entry['translation_reviewed']);self.assertEqual(entry['english_abstract'],'')
            with self.assertRaisesRegex(CollectionError,'검토 기록 누락'):
                validate_packet(pub,entry,work)
            browser.close()

    def test_cli_pending_is_neither_success_nor_failure_and_preserves_resume_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp); packet=work/'translation-review.json'
            args=parser().parse_args(['--text','KR200355113Y1','--out',tmp])
            with patch('scripts.build_references.browser_session') as session, patch('scripts.build_references.collect',side_effect=TranslationRequired(one('KR200355113Y1'),packet)):
                session.return_value.__enter__.return_value=object()
                self.assertEqual(run(args),1)
            result=json.loads(next(work.glob('처리결과_*.json')).read_text(encoding='utf-8'))[0]
            self.assertEqual(result['status'],'번역 검토 대기')
            self.assertEqual(result['review_packet'],str(packet.resolve()))
            self.assertNotIn('output_path',result)
