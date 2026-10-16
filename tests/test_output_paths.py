import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
import zipfile

from openpyxl import load_workbook
from pypdf import PdfWriter, PdfReader
from scripts.output_paths import downloads_directory, output_directory
from scripts.build_references import parser, run
from scripts.pdf_merger import merge_unique, sha256


def pdf(path, count):
    writer=PdfWriter()
    for _ in range(count):writer.add_blank_page(width=595.28,height=841.89)
    writer.write(path);writer.close()


class OutputPaths(TestCase):
    def test_windows_uses_known_folder_including_redirection(self):
        with patch('scripts.output_paths.sys.platform','win32'), patch(
                'scripts.output_paths.windows_downloads',return_value=Path('D:/Redirected/받은 파일')):
            self.assertEqual(downloads_directory(),Path('D:/Redirected/받은 파일'))

    def test_explicit_output_does_not_lookup_downloads(self):
        with tempfile.TemporaryDirectory() as tmp, patch('scripts.output_paths.downloads_directory') as detect:
            self.assertEqual(output_directory(tmp),Path(tmp).resolve())
            detect.assert_not_called()

    def test_linux_respects_config_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'user-dirs.dirs'
            target=Path(tmp)/'받은 자료'
            config.write_text(f'XDG_DOWNLOAD_DIR="{target.as_posix()}"\n',encoding='utf-8')
            with patch('scripts.output_paths.sys.platform','linux'),patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}):
                self.assertEqual(downloads_directory(),target)

    def test_collision_preserves_existing_file_and_pdf_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=root/'b.pdf';o=root/'o.pdf';pdf(b,1);pdf(o,2)
            target=root/'JP 2006-198019 A.pdf';target.write_bytes(b'keep existing')
            second=root/'JP 2006-198019 A (2).pdf';second.write_bytes(b'keep second')
            result,stats=merge_unique(b,o,target,2)
            self.assertEqual(result.name,'JP 2006-198019 A (3).pdf')
            self.assertEqual(target.read_bytes(),b'keep existing')
            self.assertEqual(second.read_bytes(),b'keep second')
            self.assertEqual(len(PdfReader(result).pages),3)
            self.assertEqual(stats['pages'],3)
            self.assertFalse(list(root.glob('*.part')))

    def test_default_batch_reports_links_and_zip_actual_collision_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'Downloads';out.mkdir()
            b=root/'b.pdf';o=root/'o.pdf';pdf(b,1);pdf(o,2)
            item=dict(source='Espacenet',biblio_pdf='b.pdf',original_pdf='o.pdf',
                biblio_url='https://worldwide.espacenet.com/publicationDetails/biblio',
                original_url='https://worldwide.espacenet.com/publicationDetails/originalDocument',original_pages=2,
                biblio_sha256=sha256(b),original_sha256=sha256(o),identity_verified=True,
                english_abstract_verified=True,full_document_verified=True,layout_verified=True,
                verification_note='Synthetic fixture only')
            mapping={key:dict(item,publication=key) for key in ['JP2006198019A','EP1234567B1']}
            manifest=root/'manifest.json';manifest.write_text(json.dumps(mapping),encoding='utf-8')
            (out/'JP 2006-198019 A.pdf').write_bytes(b'preserve')
            args=parser().parse_args(['--text','JP2006198019A,JP2006198019A,EP1234567B1',
                '--manifest',str(manifest),'--zip'])
            with patch('scripts.output_paths.downloads_directory',return_value=out):
                self.assertEqual(run(args),0)
            records=json.loads(next(out.glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(records[0]['filename'],'JP 2006-198019 A (2).pdf')
            self.assertEqual(records[0]['output_path'],records[1]['output_path'])
            for record in records:
                self.assertEqual(Path(record['output_path']).parent,out)
                self.assertEqual(sha256(record['output_path']),record['sha256'])
            workbook=load_workbook(next(out.glob('*.xlsx')))
            self.assertEqual(workbook.active['C2'].value,records[0]['filename'])
            self.assertEqual(workbook.active['C2'].hyperlink.target,Path(records[0]['output_path']).as_uri())
            with zipfile.ZipFile(next(out.glob('*.zip'))) as z:
                self.assertIn(records[0]['filename'],z.namelist())
                self.assertEqual(sum(n.endswith('.pdf') for n in z.namelist()),2)
            self.assertEqual((out/'JP 2006-198019 A.pdf').read_bytes(),b'preserve')
