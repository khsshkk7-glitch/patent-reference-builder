"""Korean national prefixes come from explicit type/kind, never digit count alone."""
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_references import parser, run, input_rows
from scripts.browser_session import CollectionError
from scripts.collector_common import Collected
from scripts.input_parser import one, resolve, korean_display_number
from scripts.kipris_collector import national_number
from scripts.original_identity import check_korean_cover, DocumentIdentityMismatch
from scripts.pdf_merger import sha256
from tests.test_core import pdf


class KoreanNumberTypes(unittest.TestCase):
    def test_reported_input_preserves_ten_and_explains_twenty_a_conflict(self):
        p = one('KR 10-2023-0061714 A')
        self.assertEqual((p.query, national_number(p)), ('pn=KR20230061714A', '1020230061714'))
        for text in ('KR 20-2023-0061714 A', '20-2023-0061714 A', 'KR2020230061714A'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, '접두부 20.*종별 A'):
                one(text, country='KR')

    def test_korean_cover_uses_publication_field_not_application_field(self):
        cover = '(12) 공개특허공보(A)\n(11) 공개번호\n(43) 공개일자\n10-2024-0164181\n2024년11월19일\n(21) 출원번호 10-2023-0061714'
        self.assertTrue(check_korean_cover(one('KR 10-2024-0164181 A'), cover))
        for wrong_cover in (cover, cover.replace('10-2024-0164181', '20-2023-0061714')):
            with self.subTest(cover=wrong_cover), self.assertRaises(DocumentIdentityMismatch):
                check_korean_cover(one('KR 10-2023-0061714 A'), wrong_cover)
        unreadable = '(12) 공개특허공보(A)\n(11) 공개번호\n(21) 출원번호 10-2023-0061714'
        requested = one('KR 10-2023-0061714 A')
        self.assertFalse(check_korean_cover(requested, unreadable))
        with self.assertRaisesRegex(CollectionError, '공보번호를 읽지 못했습니다'):
            check_korean_cover(requested, unreadable, require_readable_field=True)

    def test_wrong_right_from_collector_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong = Collected(one('KR 20-2023-0061714 U'), root/'b.pdf', root/'o.pdf', 1,
                              'KIPRIS', '', '', 'Wrong-right fixture')
            args = parser().parse_args(['--text','KR 10-2023-0061714 A','--out',tmp,'--delay','0'])
            with patch('scripts.build_references.browser_session',return_value=nullcontext(object())), \
                 patch('scripts.build_references.collect',return_value=wrong), \
                 patch('scripts.build_references.merge_unique') as merge, redirect_stdout(io.StringIO()):
                self.assertEqual(run(args),1)
            merge.assert_not_called()
            result = json.loads(next(root.glob('처리결과_*.json')).read_text(encoding='utf-8'))[0]
            self.assertEqual(result['status'],'실패')
            self.assertIn('(21) 출원번호',result['note'])

    def test_chat_splitting_retains_explicit_right_and_a_kind(self):
        args = parser().parse_args(['--text','KR 10-2007-0000036 KR 20-2007-0000036 KR 10-2020-0137353 A'])
        parsed = [one(r.value, role=r.role) for r in input_rows(args)[2]]
        self.assertEqual([p.kr_right for p in parsed], ['10','20','10'])
        self.assertEqual(parsed[-1].kind, 'A')

    def test_verified_u_publication_short_and_national_forms_agree(self):
        short = one('KR20070000036U')
        for text in ('KR 20-2007-0000036 U', 'KR2020070000036U', 'KR20070000036U'):
            with self.subTest(text=text):
                p = one(text)
                self.assertEqual(p, short)
                self.assertEqual(p.query, 'pn=KR20070000036U')
                self.assertEqual(p.filename, 'KR 20-2007-0000036 U.pdf')
                self.assertEqual(national_number(p), '2020070000036')
                self.assertEqual(korean_display_number(p), '20-2007-0000036')

    def test_application_u_marker_does_not_imply_publication_role(self):
        # This sample was observed in the Application number field of Espacenet.
        app = one('KR20040008221U', role='application')
        self.assertEqual(app.query, 'ap=KR20040008221U')
        self.assertEqual(app.filename, 'KR 20-2004-0008221 U.pdf')
        self.assertEqual(national_number(app), '2020040008221')
        with self.assertRaisesRegex(ValueError, '매핑'): resolve(app, [one('KR200355113Y1')])
        # The same trailing U cannot, by itself, determine an input's role.
        self.assertEqual(one('KR20040008221U').role, 'publication')

    def test_domestic_application_without_u_keeps_explicit_twenty_prefix(self):
        p = one('KR 20-2004-0008221', role='application')
        self.assertEqual(p.key, 'KR2020040008221')
        self.assertEqual(p.filename, 'KR 20-2004-0008221.pdf')
        self.assertEqual(national_number(p), '2020040008221')

    def test_unknown_eleven_digits_never_default_to_ten(self):
        p = one('KR20070000036')
        self.assertEqual(p.kr_right, '')
        self.assertEqual(p.filename, 'KR 2007-0000036.pdf')
        with self.assertRaisesRegex(ValueError, '권리 유형'): national_number(p)
        with self.assertRaises(ValueError):
            resolve(p, [one('KR20070000036U'), one('KR20070000036A')])

    def test_explicit_prefix_constrains_kind_resolution(self):
        utility = one('KR 20-2007-0000036')
        self.assertEqual(utility.key, 'KR20070000036')
        self.assertEqual(utility.kr_right, '20')
        self.assertEqual(resolve(utility, [one('KR20070000036A'), one('KR20070000036U')]).kind, 'U')
        patent = one('KR 10-2007-0000036')
        with self.assertRaises(ValueError): resolve(patent, [one('KR20070000036U')])
        self.assertEqual(resolve(patent, [one('KR20070000036A')]).kind, 'A')
        self.assertNotEqual(patent.cache_key, utility.cache_key)

    def test_same_digits_different_rights_do_not_reuse_cached_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); b, o = root/'b.pdf', root/'o.pdf'
            pdf(b,[595.28]); pdf(o,[595.28])
            def collect(_, requested, work, args):
                publication = one('KR20070000036A' if requested.kr_right == '10' else 'KR20070000036U')
                return Collected(publication,b,o,1,'Espacenet','https://worldwide.espacenet.com/biblio',
                                 'https://worldwide.espacenet.com/original','Synthetic type-isolation fixture')
            args = parser().parse_args(['--text','KR 10-2007-0000036,KR 20-2007-0000036', '--out',str(root/'out'),'--delay','0'])
            with patch('scripts.build_references.browser_session',return_value=nullcontext(object())), \
                 patch('scripts.build_references.collect',side_effect=collect) as collector, redirect_stdout(io.StringIO()):
                self.assertEqual(run(args),0)
            self.assertEqual(collector.call_count,2)
            records = json.loads(next(args.out.glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual([r['publication'] for r in records],['KR20070000036A','KR20070000036U'])
            self.assertEqual([r['input_kr_right'] for r in records],['10','20'])
            self.assertNotEqual(records[0]['output_path'],records[1]['output_path'])

    def test_conflicting_national_prefix_and_kind_are_rejected(self):
        for text in ('KR 10-2007-0000036 U', 'KR 20-2007-0000036 A', 'KR 20-0355113 B1', 'KR 10-1531015 Y1'):
            with self.subTest(text=text), self.assertRaises(ValueError): one(text)

    def test_existing_patents_and_registered_utility_models_are_unchanged(self):
        for text, key, filename, national in [
            ('KR 10-2020-0137353 A','KR20200137353A','KR 10-2020-0137353.pdf','1020200137353'),
            ('KR20200137353A','KR20200137353A','KR 10-2020-0137353.pdf','1020200137353'),
            ('KR 10-1531015 B1','KR101531015B1','KR 10-1531015 B1.pdf','101531015'),
            ('KR 20-0355113 Y1','KR200355113Y1','KR 20-0355113 Y1.pdf','200355113')]:
            with self.subTest(text=text):
                p = one(text)
                self.assertEqual((p.key,p.filename,national_number(p)), (key,filename,national))

    def test_epo_application_u_requires_exact_reviewed_mapping_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); b, o = root/'b.pdf', root/'o.pdf'
            pdf(b,[595.28]); pdf(o,[595.28,595.28])
            requested = one('KR20040008221U', role='application')
            entry = dict(publication='KR200355113Y1', application=requested.key, mapping_verified=True,
                mapping_note='Synthetic fixture of separately verified application and publication identities',
                source='KIPRIS',biblio_pdf=str(b),original_pdf=str(o),original_pages=2,
                biblio_url='https://www.kipris.or.kr/kpa',original_url='https://www.kipris.or.kr/original',
                biblio_sha256=sha256(b),original_sha256=sha256(o),identity_verified=True,
                english_abstract_verified=True,full_document_verified=True,layout_verified=True,
                verification_note='Synthetic mechanics only, not real source certification')
            for index, changes in enumerate(({}, {'mapping_verified':False}, {'application':'KR20040008222U'})):
                with self.subTest(changes=changes):
                    manifest = root/'manifest.json'
                    manifest.write_text(json.dumps({requested.key:dict(entry, **changes)}),encoding='utf-8')
                    args = parser().parse_args(['--text',requested.key,'--role','application','--manifest',str(manifest),
                                                '--out',str(root/f'out-{index}')])
                    with redirect_stdout(io.StringIO()): self.assertEqual(run(args), 0 if not changes else 1)
                    record = json.loads(next(args.out.glob('*.json')).read_text(encoding='utf-8'))[0]
                    self.assertEqual(record['search_query'],'ap=KR20040008221U')
                    if not changes:
                        self.assertEqual(record['publication'],'KR200355113Y1')
                        self.assertEqual(record['filename'],'KR 20-0355113 Y1.pdf')
                    else:
                        self.assertEqual(record['status'],'실패'); self.assertNotIn('output_path',record)


if __name__ == '__main__': unittest.main()
