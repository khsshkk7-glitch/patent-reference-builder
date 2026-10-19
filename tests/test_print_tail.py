import tempfile
from pathlib import Path
from unittest import TestCase
from pypdf import PdfWriter,PdfReader
from pypdf.generic import DecodedStreamObject,NameObject,ArrayObject,DictionaryObject
from scripts.collector_common import trim_blank_print_tail


class PrintTail(TestCase):
    def check_tail(self,commands,removed,annotation=False):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'print.pdf';writer=PdfWriter()
            for data in (b'0 0 20 20 re f',commands):
                page=writer.add_blank_page(width=595.28,height=841.89)
                stream=DecodedStreamObject();stream.set_data(data)
                page[NameObject('/Contents')]=writer._add_object(stream)
            if annotation:
                page[NameObject('/Annots')]=ArrayObject([DictionaryObject()])
            writer.write(path);writer.close()
            self.assertEqual(trim_blank_print_tail(path),removed)
            self.assertEqual(len(PdfReader(path).pages),2-removed)

    def test_white_browser_overflow_removed(self):
        self.check_tail(b'1 0 0 1 0 0 cm q 1 1 1 RG 1 1 1 rg /G3 gs 0 0 688 1017 re f Q',1)

    def test_black_drawing_retained(self):
        self.check_tail(b'0 0 20 20 re f',0)

    def test_text_and_image_operators_retained(self):
        self.check_tail(b'BT ET',0)
        self.check_tail(b'/Image1 Do',0)

    def test_annotation_retained(self):
        self.check_tail(b'1 g 0 0 20 20 re f',0,annotation=True)

    def test_colour_restored_after_graphics_state_pop(self):
        self.check_tail(b'q 1 g 0 0 20 20 re f Q 0 0 20 20 re f',0)
