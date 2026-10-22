import base64,io,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from playwright.sync_api import sync_playwright
from scripts.kipris_collector import collect_domestic,domestic_number_matches
from scripts.input_parser import one


def fixture_pdf(number):
    writer=PdfWriter();page=writer.add_blank_page(width=595.28,height=841.89)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 30 780 Td ({number}) Tj ET'.encode())
    page[NameObject('/Contents')]=writer._add_object(stream)
    writer.add_blank_page(width=595.28,height=841.89)
    buffer=io.BytesIO();writer.write(buffer);writer.close();return buffer.getvalue()


class KiprisDomestic(TestCase):
    def test_registration_serial_suffix_is_exact(self):
        self.assertTrue(domestic_number_matches('1015310150000 (2015.06.17)','101531015','B1'))
        self.assertFalse(domestic_number_matches('1015310150001','101531015','B1'))
        self.assertFalse(domestic_number_matches('10202001373530000','1020200137353','A'))
        self.assertTrue(domestic_number_matches('2003551130000','200355113','Y1'))
        self.assertFalse(domestic_number_matches('2003551130001','200355113','Y1'))

    def test_exact_publication_row_nonzero_viewer_and_registered_tab(self):
        with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
            browser=pw.chromium.launch();context=browser.new_context()
            for key,number,cover,tab in [('KR20200137353A','1020200137353','10-2020-0137353','공개전문'),
                                         ('KR101531015B1','101531015','10-1531015','공고전문'),
                                         ('KR200355113Y1','200355113','20-0355113','공고전문'),
                                         ('KR20070000036U','2020070000036','20-2007-0000036','공개전문')]:
                with self.subTest(key=key):
                    blob=base64.b64encode(fixture_pdf(cover)).decode()
                    field='등록번호(일자)' if tab=='공고전문' else '공개번호(일자)'
                    serial='0000' if tab=='공고전문' else ''
                    html=f'''<meta charset="utf-8"><div id="patentTabPannel"><a href="#">국내</a></div>
                    <section id="resultSection"><article id="divViewSel">1020190063559<button>[1] fixture</button></article></section>
                    <div id="mainResultDetail"><table><tr><th scope="row">{field}</th><td>{number}{serial}</td></tr>
                    <tr><th scope="row">국제공개번호(일자)</th><td>Unrelated</td></tr></table>
                    <button onclick="openPdf()">{tab}</button></div>
                    <script>function openPdf(){{const bytes=Uint8Array.from(atob('{blob}'),c=>c.charCodeAt(0));
                    const file=URL.createObjectURL(new Blob([bytes],{{type:'application/pdf'}}));
                    const frame=document.createElement('iframe');frame.src='/viewer?file='+encodeURIComponent(file);document.querySelector('#mainResultDetail').append(frame);}}</script>'''
                    page=context.new_page();page.set_default_timeout(3000)
                    def route(r):
                        if '/viewer?' in r.request.url:
                            return r.fulfill(content_type='text/html',body="<span id='numPages'>/ 0</span><script>setTimeout(()=>document.querySelector('#numPages').textContent='/ 2',100)</script>")
                        r.fulfill(content_type='text/html',body=html)
                    page.route('**/*',route)
                    page.goto('https://www.kipris.or.kr/fixture')
                    work=Path(tmp)/key;work.mkdir()
                    result=collect_domestic(page,one(key),'1020190063559',number,work/'biblio.pdf',page.url,work,SimpleNamespace())
                    self.assertEqual(result.source,'KIPRIS');self.assertEqual(result.original_pages,2)
                    self.assertEqual(result.original.read_bytes(),base64.b64decode(blob))
                    page.close()
            context.close();browser.close()
