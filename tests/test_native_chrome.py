from pathlib import Path
from unittest import TestCase
from unittest.mock import patch,MagicMock
from scripts.native_chrome import native_chrome
from scripts.build_references import parser,run


class NativeChrome(TestCase):
    def test_local_connection_task_profile_and_owned_process_cleanup(self):
        process=MagicMock();process.poll.return_value=None
        response=MagicMock();response.__enter__.return_value.status=200
        with patch('scripts.native_chrome.chrome_executable',return_value='chrome.exe'), \
             patch('scripts.native_chrome.subprocess.Popen',return_value=process) as launch, \
             patch('scripts.native_chrome.urlopen',return_value=response) as request:
            with native_chrome() as endpoint:
                self.assertTrue(endpoint.startswith('http://127.0.0.1:'))
                request.assert_called_once_with(endpoint+'/json/version',timeout=1)
                command=launch.call_args.args[0]
                self.assertIn('--remote-debugging-address=127.0.0.1',command)
                profile=next(x.split('=',1)[1] for x in command if x.startswith('--user-data-dir='))
                self.assertTrue(Path(profile).is_dir())
                self.assertFalse(any('disable-web-security' in x or 'user-agent' in x or 'AutomationControlled' in x for x in command))
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=5)

    def test_native_mode_rejects_conflicting_settings(self):
        for options in (['--native-chrome'],['--native-chrome','--headed','--profile','profile'],
                        ['--native-chrome','--headed','--cdp','http://localhost:9222'],
                        ['--native-chrome','--headed','--channel','msedge']):
            args=parser().parse_args(['--text','KR20200137353A']+options)
            with self.assertRaisesRegex(ValueError,'native-chrome'):run(args)

    def test_no_fallback_requires_kipris(self):
        args=parser().parse_args(['--text','JP2004121879A','--no-fallback'])
        with self.assertRaisesRegex(ValueError,'source kipris'):run(args)
