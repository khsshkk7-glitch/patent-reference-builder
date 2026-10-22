"""Explicit number types apply to files; contradictory headers never silently win."""
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from scripts.build_references import parser, run, input_rows
from scripts.input_parser import one
from scripts.pdf_merger import sha256
from tests.test_core import pdf


class InputRole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def table(self, suffix, rows):
        path = self.root / ('input' + suffix)
        if suffix == '.csv':
            import csv
            with path.open('w', encoding='utf-8-sig', newline='') as handle: csv.writer(handle).writerows(rows)
        elif suffix == '.xlsx':
            wb = Workbook()
            for row in rows: wb.active.append(row)
            wb.save(path)
        else:
            import xlwt
            wb = xlwt.Workbook(); ws = wb.add_sheet('data')
            for i, row in enumerate(rows):
                for j, value in enumerate(row): ws.write(i, j, value)
            wb.save(str(path))
        return path

    def args(self, path, *extra):
        return parser().parse_args(['--input',str(path),'--out',str(self.root / 'out'), *extra])

    def test_headerless_files_use_explicit_application_all_formats(self):
        for suffix in ('.csv', '.xlsx', '.xls'):
            with self.subTest(suffix=suffix):
                path = self.table(suffix, [('KR 20-2004-0008221',)])
                args = self.args(path, '--role','application','--dry-run')
                with redirect_stdout(io.StringIO()): self.assertEqual(run(args), 0)
                plan = json.loads((args.out / 'input-plan.json').read_text(encoding='utf-8'))
                self.assertEqual(plan[0]['query'], 'ap=KR2020040008221')
                self.assertEqual(plan[0]['input_role_source'], 'explicit')

    def test_unspecified_preserves_header_detection_and_chat_default(self):
        for header, role in [('출원번호','application'), ('Application No.','application'),
                             ('Publication No.','publication'), ('특허번호','publication')]:
            path = self.table('.xlsx', [(header,), ('KR 20-2004-0008221',)])
            args = self.args(path)
            self.assertIsNone(args.role)
            self.assertEqual(input_rows(args)[2][0].role, role)
        for text, extra, role in [('JP2006198019A', [], 'publication'),
                                  ('KR 20-2004-0008221', ['--role','application'], 'application')]:
            row = input_rows(parser().parse_args(['--text',text,*extra]))[2][0]
            self.assertEqual(row.role, role)
        path = self.table('.csv', [('KR 20-2004-0008221',)])
        self.assertEqual(input_rows(self.args(path))[2][0].role, 'publication')

    def test_neutral_header_accepts_explicit_role(self):
        for header in ('特許番号', '특허번호', 'Patent No.', '내 번호'):
            path = self.table('.xlsx', [(header,), ('KR 20-2004-0008221',)])
            row = input_rows(self.args(path, '--column',header,'--role','application'))[2][0]
            self.assertFalse(row.input_error)
            self.assertEqual(one(row.value, role=row.role).query, 'ap=KR2020040008221')

    def test_conflicting_header_reports_failure_without_browser(self):
        for suffix in ('.csv', '.xlsx', '.xls'):
            for header, role in [('공개번호','application'), ('출원번호','publication')]:
                with self.subTest(suffix=suffix, header=header):
                    path = self.table(suffix, [(header,), ('KR 20-2004-0008221',)])
                    args = self.args(path, '--role',role,'--dry-run')
                    with redirect_stdout(io.StringIO()): self.assertEqual(run(args), 1)
                    plan = json.loads((args.out / 'input-plan.json').read_text(encoding='utf-8'))
                    self.assertIn('충돌', plan[0]['error']); self.assertIsNone(plan[0]['query'])
                    args.dry_run = False
                    with patch('scripts.build_references.browser_session') as browser, redirect_stdout(io.StringIO()):
                        self.assertEqual(run(args), 1)
                        browser.assert_not_called()

    def test_matching_role_selects_matching_column_and_respects_column_conflict(self):
        path = self.table('.csv', [('공개번호','출원번호'), ('KR20200137353A','KR2020040008221')])
        row = input_rows(self.args(path, '--role','application'))[2][0]
        self.assertEqual(row.value, 'KR2020040008221'); self.assertFalse(row.input_error)
        row = input_rows(self.args(path))[2][0]
        self.assertEqual(row.value, 'KR20200137353A')
        row = input_rows(self.args(path, '--column','공개번호','--role','application'))[2][0]
        self.assertIn('충돌', row.input_error)

    def test_online_collector_receives_application_role_not_publication(self):
        path = self.table('.csv', [('KR 20-2004-0008221',)])
        args = self.args(path, '--role','application')
        with patch('scripts.build_references.browser_session', return_value=nullcontext(object())), \
             patch('scripts.build_references.collect', side_effect=ValueError('Mapping review required')) as collector, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 1)
        requested = collector.call_args.args[1]
        self.assertEqual(requested.role, 'application')
        self.assertEqual(requested.query, 'ap=KR2020040008221')

    def test_application_file_resume_requires_verified_application_mapping(self):
        b, o = self.root / 'b.pdf', self.root / 'o.pdf'
        pdf(b, [595.28]); pdf(o, [595.28, 595.28])
        entry = dict(publication='KR200355113Y1', source='KIPRIS', application='KR2020040008221',
            mapping_verified=True, mapping_note='Synthetic mapping fixture only', biblio_pdf=str(b), original_pdf=str(o),
            biblio_url='https://www.kipris.or.kr/kpa', original_url='https://www.kipris.or.kr/original', original_pages=2,
            biblio_sha256=sha256(b), original_sha256=sha256(o), identity_verified=True,
            english_abstract_verified=True, full_document_verified=True, layout_verified=True,
            verification_note='Synthetic source parts, not real patent certification')
        path = self.table('.csv', [('KR 20-2004-0008221',)])
        manifest = self.root / 'manifest.json'
        for changes, expected in [({}, 0), ({'mapping_verified':False}, 1), ({'application':'KR2020040008222'}, 1)]:
            with self.subTest(changes=changes):
                manifest.write_text(json.dumps({'KR2020040008221':dict(entry, **changes)}), encoding='utf-8')
                args = self.args(path, '--role','application','--manifest',str(manifest))
                with patch('scripts.build_references.browser_session') as browser, redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(run(args), expected); browser.assert_not_called()
                summary = json.loads(stdout.getvalue().splitlines()[-1])
                records = json.loads(Path(summary['report']).with_suffix('.json').read_text(encoding='utf-8'))
                self.assertEqual(records[0]['search_query'], 'ap=KR2020040008221')
                if expected == 0:
                    self.assertEqual(records[0]['publication'], 'KR200355113Y1')
                    self.assertEqual(records[0]['filename'], 'KR 20-0355113 Y1.pdf')
                else:
                    self.assertEqual(records[0]['status'], '실패')
                    self.assertNotIn('output_path', records[0])


if __name__ == '__main__': unittest.main()
