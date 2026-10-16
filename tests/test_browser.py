"""Deterministic browser contract tests; no requests leave the browser routes."""
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfWriter, PdfReader
from playwright.sync_api import sync_playwright
from scripts.espacenet_collector import collect, START
from scripts.input_parser import one

ABSTRACT = 'A storage shelf comprises a back plate and multiple shelf boards. Lighting devices illuminate reflecting members to reduce deterioration of stored articles and provide a comfortable appearance.'


class BrowserContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def test_espacenet_print_and_complete_download(self):
        self.check_download(interactive=False)

    def test_interactive_download_continues_without_restarting_search(self):
        self.check_download(interactive=True)

    def check_download(self, interactive):
        with tempfile.TemporaryDirectory() as tmp:
            context = self.browser.new_context()
            def route(r):
                url = r.request.url
                if 'flavour=trueFull' in url:
                    w=PdfWriter();w.add_blank_page(width=595.28,height=841.89);w.add_blank_page(width=595.28,height=841.89)
                    out=io.BytesIO();w.write(out);w.close()
                    return r.fulfill(body=out.getvalue(),content_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="original.pdf"'})
                if 'advancedSearch' in url:
                    html='<input id="pnEditBox"><button onclick="location.href=\'/results\'">Search</button>'
                elif '/results' in url:
                    html='<a id="publicationId1" href="/biblio">Storage shelf</a>'
                elif '/biblio' in url:
                    html=f'''<div id="pagebody"><h1>Bibliographic data: JP2006198019 (A)</h1>
                    <div id="inventorsRow">Example Inventor</div><div id="applicantsRow">Example Applicant</div>
                    <div class="application article"><h3>Abstract of JP2006198019 (A)</h3><p>{ABSTRACT}</p></div></div>
                    <a href="/original">Original document</a>'''
                else:
                    html='''<div id="pagebody"><h1>Original document: JP2006198019 (A)</h1>
                    <select id="navigationSelector"><option>1/2 Abstract Bibliography</option><option>2/2 Drawings</option></select>
                    <a href="/data/doc.pdf?flavour=trueFull&amp;CC=JP&amp;NR=2006198019A&amp;KC=A">Download</a></div>'''
                r.fulfill(body=html,content_type='text/html')
            context.route('**/*',route)
            page=context.new_page();page.set_default_timeout(3000)
            result=collect(page,one('JP 2006-198019 A'),Path(tmp),SimpleNamespace(
                retries=1,timeout=3,interactive=interactive,human_timeout=3))
            self.assertEqual(result.original_pages,2)
            self.assertIn(ABSTRACT, ' '.join(p.extract_text() for p in PdfReader(result.biblio).pages).replace('\n',' '))
            self.assertEqual(len(PdfReader(result.original).pages),2)
            context.close()
