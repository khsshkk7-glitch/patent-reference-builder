"""Optional local sample regression. Never distribute the user's sample PDFs."""
import os
from pathlib import Path
import tempfile
import unittest
from pypdf import PdfReader, PdfWriter
from scripts.pdf_merger import merge


@unittest.skipUnless(os.getenv('PATENT_SAMPLE_DIR'), 'Set PATENT_SAMPLE_DIR for private local sample tests')
class Samples(unittest.TestCase):
    def test_sample_merges_preserve_every_source_page(self):
        root=Path(os.environ['PATENT_SAMPLE_DIR'])
        # KR sample includes a file-attachment notice after its KPA page.
        for name,start,total in [('JP 2006-198019 A.pdf',1,10),('KR 10-2020-0137353.pdf',2,20)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                r=PdfReader(root/name);b=Path(tmp)/'b.pdf';o=Path(tmp)/'o.pdf';out=Path(tmp)/name
                w=PdfWriter();w.add_page(r.pages[0]);w.write(b);w.close()
                w=PdfWriter()
                for page in r.pages[start:]: w.add_page(page)
                w.write(o);w.close()
                stats=merge(b,o,out,len(r.pages)-start)
                self.assertEqual(stats['pages'],total)
                merged=PdfReader(out)
                # Compare decoded content streams; original text/images are not reprinted.
                for i,page in enumerate(r.pages[start:],1):
                    self.assertEqual(merged.pages[i].get_contents().get_data(),page.get_contents().get_data())
