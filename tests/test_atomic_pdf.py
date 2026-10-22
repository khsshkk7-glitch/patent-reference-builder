"""Fault injection and real concurrent publication must never expose partial PDFs."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
import zipfile

from scripts import pdf_merger as merger
from scripts.build_references import parser, run
from tests.test_core import pdf


class AtomicPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.b = self.root / 'bibliography.pdf'
        self.o = self.root / 'original.pdf'
        pdf(self.b, [595.28]); pdf(self.o, [400, 500])
        self.out = self.root / 'output' / 'JP 2006-198019 A.pdf'

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, mode):
        if mode == 'copy':
            return merger.copy_original_unique(self.o, self.out, 2)
        return merger.merge_unique(self.b, self.o, self.out, 2)

    def assert_no_output(self):
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.out.parent.glob('*.pdf')))
        self.assertFalse(list(self.out.parent.glob('*.part')))

    def test_partial_write_failure_cleanup_and_retry_both_modes(self):
        original_open = Path.open
        test = self

        class Interrupted:
            def __init__(self, path): self.handle = original_open(path, 'wb')
            def __enter__(self): return self
            def __exit__(self, *args): self.handle.close()
            def __getattr__(self, name): return getattr(self.handle, name)
            def write(self, data):
                self.handle.write(data[:64]); self.handle.flush()
                test.assertFalse(test.out.exists())
                raise OSError('simulated interrupted write')

        def open_file(path, mode='r', *args, **kwargs):
            if path.name.endswith('.pdf.part') and mode == 'wb':
                return Interrupted(path)
            return original_open(path, mode, *args, **kwargs)

        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode):
                with patch.object(Path, 'open', open_file):
                    with self.assertRaisesRegex(OSError, 'interrupted'):
                        self.save(mode)
                self.assert_no_output()
                actual, stats = self.save(mode)
                self.assertEqual(actual, self.out)  # No false (2) after failure.
                self.assertEqual(stats['sha256'], merger.sha256(actual))
                actual.unlink()

    def test_flush_failure_never_publishes_both_modes(self):
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode), patch.object(merger.os, 'fsync', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'): self.save(mode)
            self.assert_no_output()

    def test_revalidation_failure_never_publishes_both_modes(self):
        inspect = merger.inspect_pdf
        def invalid(path):
            if Path(path).name.endswith('.pdf.part'): raise ValueError('invalid saved PDF')
            return inspect(path)
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode), patch.object(merger, 'inspect_pdf', side_effect=invalid):
                with self.assertRaisesRegex(ValueError, 'invalid saved'): self.save(mode)
            self.assert_no_output()

    def test_hash_failure_never_publishes_both_modes(self):
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode), patch.object(merger, 'sha256', side_effect=OSError('hash read error')):
                with self.assertRaisesRegex(OSError, 'hash read error'): self.save(mode)
            self.assert_no_output()

    def test_publication_failure_preserves_existing_and_cleans_temp(self):
        self.out.parent.mkdir()
        self.out.write_bytes(b'user file, must preserve')
        link = os.link
        def fail_link(src, dst):
            if Path(dst) == self.out: return link(src, dst)  # real FileExistsError
            raise OSError('link unavailable')
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode), patch.object(merger.os, 'link', side_effect=fail_link):
                with self.assertRaisesRegex(OSError, 'link unavailable'): self.save(mode)
            self.assertEqual(self.out.read_bytes(), b'user file, must preserve')
            self.assertEqual(list(self.out.parent.glob('*.pdf')), [self.out])
            self.assertFalse(list(self.out.parent.glob('*.part')))

    def test_collision_after_validation_keeps_rival_file_both_modes(self):
        link = os.link
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode):
                def race(src, dst):
                    if Path(dst) == self.out:
                        link(self.o, dst)  # Another complete result arrives at the last instant.
                    return link(src, dst)
                with patch.object(merger.os, 'link', side_effect=race):
                    actual, stats = self.save(mode)
                self.assertEqual(self.out.read_bytes(), self.o.read_bytes())
                self.assertEqual(actual.name, 'JP 2006-198019 A (2).pdf')
                self.assertEqual(stats['pages'], 2 if mode == 'copy' else 3)
                self.assertEqual(stats['sha256'], merger.sha256(actual))
                self.assertFalse(list(self.out.parent.glob('*.part')))
                self.out.unlink(); actual.unlink()

    def test_real_concurrent_saves_have_unique_complete_files_both_modes(self):
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode):
                barrier = Barrier(4)
                def save(_):
                    barrier.wait(timeout=10)
                    return self.save(mode)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(save, range(4)))
                self.assertEqual(len({p for p, _ in results}), 4)
                for path, stats in results:
                    self.assertEqual(len(merger.inspect_pdf(path).pages), 2 if mode == 'copy' else 3)
                    self.assertEqual(stats['sha256'], merger.sha256(path))
                    if mode == 'copy': self.assertEqual(path.read_bytes(), self.o.read_bytes())
                    path.unlink()
                self.assertFalse(list(self.out.parent.glob('*.part')))

    def test_final_name_only_appears_after_validation(self):
        link = os.link
        for mode in ('merge', 'copy'):
            with self.subTest(mode=mode):
                def observe(src, dst):
                    self.assertFalse(Path(dst).exists())
                    reader = merger.inspect_pdf(src)
                    self.assertEqual(len(reader.pages), 2 if mode == 'copy' else 3)
                    link(src, dst)
                    self.assertEqual(Path(src).read_bytes(), Path(dst).read_bytes())
                with patch.object(merger.os, 'link', side_effect=observe): self.save(mode)
                self.out.unlink()

    def test_cli_failed_save_is_not_in_success_zip(self):
        item = dict(publication='JP2006198019A', source='Espacenet',
                    biblio_pdf=str(self.b), original_pdf=str(self.o), original_pages=2,
                    biblio_url='https://worldwide.espacenet.com/publicationDetails/biblio',
                    original_url='https://worldwide.espacenet.com/publicationDetails/originalDocument',
                    biblio_sha256=merger.sha256(self.b), original_sha256=merger.sha256(self.o),
                    identity_verified=True, english_abstract_verified=True, full_document_verified=True,
                    layout_verified=True, verification_note='Synthetic storage fault test only')
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'JP2006198019A': item}), encoding='utf-8')
        args = parser().parse_args(['--text', 'JP2006198019A', '--manifest', str(manifest),
                                   '--out', str(self.out.parent), '--zip'])
        with patch.object(merger.os, 'link', side_effect=OSError('simulated publication failure')):
            with redirect_stdout(io.StringIO()): self.assertEqual(run(args), 1)
        self.assert_no_output()
        rows = json.loads(next(self.out.parent.glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(rows[0]['status'], '실패')
        self.assertNotIn('output_path', rows[0])
        with zipfile.ZipFile(next(self.out.parent.glob('*.zip'))) as z:
            self.assertFalse(any(n.endswith('.pdf') for n in z.namelist()))


if __name__ == '__main__': unittest.main()
