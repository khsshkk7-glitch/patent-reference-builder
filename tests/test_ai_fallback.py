import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from reportlab.pdfgen import canvas

from scripts.ai_fallback import validate_packet, from_ai_packet
from scripts.browser_session import CollectionError
from scripts.build_references import parser, run
from scripts.input_parser import one
from scripts.pdf_merger import sha256, inspect_pdf


class AiFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root/'original.pdf'
        c = canvas.Canvas(str(self.original))
        for page in range(2):
            c.drawString(50,700,f'JP3102826U original page {page+1}'); c.showPage()
        c.save()
        self.pub = one('JP3102826U')
        self.entry = dict(publication=self.pub.key, translation_type='ai_translation', source_abstract_available=True,
            source_kind='abstract', source_language='Japanese', source_text='日本語の原文要約', source_pages=[1],
            english_abstract='A display fixture has removable exterior panels mounted on a supporting structure. The structure can be reused when the decoration is changed.',
            original_source='Espacenet', original_url='https://worldwide.espacenet.com/publicationDetails/originalDocument?CC=JP&NR=3102826U&KC=U',
            original_pdf='original.pdf',original_sha256=sha256(self.original),original_pages=2,viewer_pages=2,
            identity_verified=True,full_document_verified=True,source_text_verified=True,translation_reviewed=True,
            review_note='Compared to the original abstract on page 1.', official_english_unavailable_reason='Exact record abstract unavailable.',
            bibliography=[['Publication','JP 3102826 U'],['Title','Display fixture'],['Applicant / Right holder','Example Co.'],['Inventor / Creator','Example Person']])

    def test_rejects_wrong_publication_hash_and_unreviewed_source(self):
        for changes in ({'publication':'JP3102826B'}, {'original_sha256':'0'*64}, {'source_text_verified':False},
                        {'viewer_pages':1}, {'source_pages':[3]}, {'translation_type':'official'},
                        {'original_url':self.entry['original_url'].replace('KC=U','KC=B')}):
            with self.subTest(changes=changes), self.assertRaises((CollectionError, ValueError)):
                validate_packet(self.pub,dict(self.entry,**changes),self.root)

    def test_translation_and_summary_cannot_be_mislabelled(self):
        with self.assertRaises(CollectionError):
            validate_packet(self.pub,dict(self.entry,source_abstract_available=False),self.root)
        summary = dict(self.entry,translation_type='ai_summary',source_abstract_available=False,source_kind='description')
        work=self.root/'summary';work.mkdir()
        parts=from_ai_packet(self.pub,summary,self.root,work)
        text=''.join(p.extract_text() for p in inspect_pdf(parts.biblio).pages)
        self.assertIn('AI-GENERATED SUMMARY',text)
        self.assertNotIn('AI-translated abstract',text)

    def test_ai_pipeline_keeps_original_pages_and_reports_separate_success(self):
        manifest=self.root/'ai.json'; manifest.write_text(json.dumps({self.pub.key:self.entry}),encoding='utf-8')
        out=self.root/'out'
        args=parser().parse_args(['--text','JP3102826U,JP3102826U','--ai-manifest',str(manifest),'--out',str(out),'--zip'])
        with patch('scripts.build_references.browser_session',side_effect=AssertionError('No live browser needed')):
            self.assertEqual(run(args),0)
        rows=json.loads(next(out.glob('처리결과_*.json')).read_text(encoding='utf-8'))
        self.assertEqual([r['status'] for r in rows],['AI 번역 보완']*2)
        self.assertFalse(rows[0]['complete_reference'])
        self.assertEqual(rows[0]['ai_provenance']['source_text'],self.entry['source_text'])
        self.assertEqual(rows[0]['output_path'],rows[1]['output_path'])
        result=inspect_pdf(rows[0]['output_path']); original=inspect_pdf(self.original)
        self.assertEqual(len(result.pages),rows[0]['biblio_pages']+2)
        for i,p in enumerate(original.pages):
            self.assertEqual(p.get_contents().get_data(),result.pages[rows[0]['biblio_pages']+i].get_contents().get_data())
        with zipfile.ZipFile(next(out.glob('AI보완참증_*.zip'))) as archive:
            self.assertEqual(sum(n.endswith('.pdf') for n in archive.namelist()),1)


if __name__ == '__main__':
    unittest.main()
