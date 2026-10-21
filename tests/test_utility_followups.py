import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from scripts.input_parser import one, resolve
from scripts.excel_reporter import read_table
from scripts.kipris_collector import choose_domestic_record, collect_domestic_for_translation, TranslationRequired
from scripts.collector_common import Collected
from scripts.browser_session import CollectionError
from tests.test_kipris_domestic import fixture_pdf


def html(numbers, abstract='한국어 원문 초록 내용'):
    articles=''.join(f'<article><button onclick="document.querySelector(\'#reg\').textContent=\'{n}\'">[{i+1}] candidate</button></article>' for i,n in enumerate(numbers))
    return f'''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">국내</a></div>
    <input id="queryText"><button>검색</button><section id="resultSection">{articles}</section>
    <div id="mainResultDetail"><button>상세정보</button><table><tr><th scope="row">등록번호(일자)</th><td id="reg">{numbers[0]}</td></tr></table>
    <div id="sum_all">요약 {abstract}</div></div>'''


class UtilityFollowups(TestCase):
    def test_national_utility_numbers_keep_right_prefix_and_role(self):
        for text in ('KR 20-2004-0008221','KR2020040008221','KR 20 2004 0008221'):
            p=one(text,role='application')
            self.assertEqual(p.key,'KR2020040008221');self.assertEqual(p.query,'ap=KR2020040008221')
            self.assertEqual(p.filename,'KR 20-2004-0008221.pdf')
            with self.assertRaises(ValueError): resolve(p,[one('KR200355113Y1')])
        self.assertEqual(one('KR1020200137353A').key,'KR20200137353A')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.xlsx'; w=Workbook();w.active.append(['출원번호']);w.active.append(['KR 20-2004-0008221']);w.save(path)
            row=read_table(path)[2][0]
            self.assertEqual(row.role,'application');self.assertEqual(one(row.value,role=row.role).key,'KR2020040008221')

    def test_multiple_candidates_exact_field_selection_and_ambiguity(self):
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
            browser=pw.chromium.launch(); page=browser.new_page();page.set_default_timeout(2000)
            for numbers, count in [(['2003551130000','1015310150000'],1),(['1015310150000','2003551130000'],1),(['1015310150000'],0),(['2003551130000','2003551130000'],2)]:
                page.set_content(html(numbers))
                if count==1:
                    choose_domestic_record(page,one('KR200355113Y1'),'200355113',Path(tmp))
                    self.assertEqual(page.locator('#reg').inner_text(),'2003551130000')
                else:
                    with self.assertRaisesRegex(CollectionError,f'후보 {count}건'):
                        choose_domestic_record(page,one('KR200355113Y1'),'200355113',Path(tmp))
            browser.close()

    def test_missing_web_abstract_preserves_original_without_inventing_summary(self):
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
            browser=pw.chromium.launch();page=browser.new_page();page.set_default_timeout(2000)
            page.route('**/*',lambda r:r.fulfill(body=html(['2003551130000'],''),content_type='text/html; charset=utf-8'))
            work=Path(tmp);original=work/'original.pdf';original.write_bytes(fixture_pdf('20-0355113'))
            parts=Collected(one('KR200355113Y1'),None,original,2,'KIPRIS','https://www.kipris.or.kr/','https://www.kipris.or.kr/','')
            with patch('scripts.kipris_collector.download_domestic_pane',return_value=parts) as download:
                with self.assertRaises(TranslationRequired):
                    collect_domestic_for_translation(page,parts.publication,work,SimpleNamespace(retries=1))
                download.assert_called_once()
            entry=json.loads((work/'translation-review.json').read_text(encoding='utf-8'))[parts.publication.key]
            self.assertIsNone(entry['source_abstract_available'])
            self.assertEqual(entry['translation_type'],'review_required')
            self.assertEqual(entry['source_pages'],[])
            self.assertFalse(entry['translation_reviewed'])
            self.assertEqual(len(list(work.glob('original-page-*.txt'))),2)
            self.assertEqual(original.read_bytes(),fixture_pdf('20-0355113'))
            browser.close()
