import unittest
from types import SimpleNamespace
from scripts.input_parser import one
from scripts.browser_session import CollectionError
from scripts.jplatpat_supplement import validate_source_url, validate_snapshot, document_html, run, NOTICE


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.p = one('JP3102826U')
        self.url = 'https://www.j-platpat.inpit.go.jp/c1801/PU/JP-3102826/25/en'
        self.data = dict(identity='JP,3102826,U', notice='JPO and INPIT\n' + NOTICE,
            bibliography='(73) [Owner]\n[Name]Example Co.\n(72) [Creator]\n[Name]Example Person',
            overview='[Problem] Reuse.\n[Means for solving] Detachable panel.',
            images=[dict(src='https://www.j-platpat.inpit.go.jp/gazette_work/example.png', loaded=True)])

    def test_opt_in_required_before_network(self):
        with self.assertRaisesRegex(ValueError, '명시적으로'):
            run(SimpleNamespace(acknowledge_machine_translation=False))

    def test_exact_official_u_url(self):
        validate_source_url(self.url, self.p)
        for url in (self.url.replace('/25/', '/20/'), self.url.replace('3102826', '3102827'),
                    self.url.replace('www.j-platpat.inpit.go.jp', 'example.org')):
            with self.assertRaises(ValueError):
                validate_source_url(url, self.p)
        with self.assertRaises(ValueError):
            validate_source_url(self.url, one('JP3102826B'))

    def test_missing_or_incomplete_translation_rejected(self):
        validate_snapshot(self.data, self.p)
        for field, value in [('identity', 'JP,3102826,B'), ('notice', ''), ('images', []),
                             ('bibliography', '(73) [Owner]\n(72) [Creator]\n[Name]Only creator')]:
            with self.assertRaises(CollectionError):
                validate_snapshot(dict(self.data, **{field:value}), self.p)

    def test_notice_label_and_source_text_preserved(self):
        html = document_html(self.data, self.p, self.url)
        for required in (NOTICE, 'NOT A COMPLETE REFERENCE', '완성 참증 아님', self.url, '[Problem] Reuse.'):
            self.assertIn(required, html)


if __name__ == '__main__':
    unittest.main()
