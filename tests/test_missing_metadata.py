from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock,patch
import json,zipfile
from pypdf import PdfWriter
from playwright.sync_api import sync_playwright
from scripts.browser_session import MetadataUnavailable
from scripts.input_parser import one
from scripts.espacenet_collector import collect
from scripts.collector_common import Collected
from scripts.build_references import parser,run

PUBLICATION=one('JP3102826U')
URL='https://worldwide.espacenet.com/publicationDetails/biblio?CC=JP&NR=3102826U&KC=U'
FIELDS=('title','inventors','applicants','english_abstract')
HTML='''<div id="pagebody"><h1>Bibliographic data: JP3102826 (U)</h1>
<span id="bookmarkTitle">No title available</span><div id="inventorsRow"></div><div id="applicantsRow"></div>
<div class="application article"><h3>Abstract not available for JP3102826 (U)</h3></div></div>
<a href="/original">Original document</a>'''


class MissingMetadata(TestCase):
    def test_utility_model_lists_every_gap_and_does_not_create_reference(self):
        with sync_playwright() as pw, TemporaryDirectory() as tmp:
            browser=pw.chromium.launch();page=browser.new_page()
            page.route('**/*',lambda r:r.fulfill(body=HTML,content_type='text/html'))
            page.goto(URL)
            with patch('scripts.espacenet_collector.open_record',return_value=PUBLICATION), \
                 patch('scripts.espacenet_collector.download_original') as download:
                with self.assertRaises(MetadataUnavailable) as error:
                    collect(page,PUBLICATION,Path(tmp),None)
            self.assertEqual(error.exception.diagnostics[0]['missing_fields'],list(FIELDS))
            self.assertTrue(error.exception.diagnostics[0]['original_link_present'])
            self.assertFalse(error.exception.diagnostics[0]['original_download_verified'])
            download.assert_not_called();self.assertFalse(list(Path(tmp).glob('*.pdf')))
            browser.close()

    def test_failure_report_keeps_structured_gaps_and_no_success_pdf(self):
        with TemporaryDirectory() as tmp:
            page=MagicMock();page.content.return_value='fixture'
            args=parser().parse_args(['--text','JP3102826U','--out',tmp,'--zip'])
            with patch('scripts.build_references.browser_session',return_value=nullcontext(page)), \
                 patch('scripts.espacenet_collector.collect',side_effect=MetadataUnavailable(PUBLICATION,URL,FIELDS,True)):
                self.assertEqual(run(args),1)
            result=json.loads(next(Path(tmp).glob('*.json')).read_text(encoding='utf-8'))[0]
            self.assertEqual(result['error_code'],'OFFICIAL_DATA_MISSING')
            self.assertEqual(set(result['missing_fields']),set(FIELDS))
            self.assertFalse(result['complete_reference'])
            self.assertEqual(result['status'],'실패')
            self.assertNotIn('영문 초록 확보 성공',result['note'])
            with zipfile.ZipFile(next(Path(tmp).glob('*.zip'))) as archive:
                self.assertFalse(any(n.endswith('.pdf') for n in archive.namelist()))

    def test_original_only_is_separate_and_bytes_are_preserved(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'fixture.pdf'
            writer=PdfWriter();writer.add_blank_page(width=595.28,height=841.89);writer.write(original);writer.close()
            parts=Collected(PUBLICATION,None,original,1,'Espacenet',URL,URL,
                '원문 단독 수집; 완성 참증 아님',FIELDS)
            args=parser().parse_args(['--text','JP3102826U','--original-only','--out',str(root/'out'),'--zip','--delay','0'])
            with patch('scripts.build_references.browser_session',return_value=nullcontext(object())), \
                 patch('scripts.espacenet_collector.collect_original_only',return_value=parts):
                self.assertEqual(run(args),0)
            result=json.loads(next((root/'out').glob('*.json')).read_text(encoding='utf-8'))[0]
            self.assertEqual(result['status'],'원문만')
            self.assertFalse(result['complete_reference'])
            output=Path(result['output_path'])
            self.assertEqual(output.parent.name,'원문만');self.assertEqual(output.read_bytes(),original.read_bytes())
            with zipfile.ZipFile(next((root/'out').glob('*.zip'))) as archive:
                self.assertIn('원문만/JP 3102826 U.pdf',archive.namelist())
