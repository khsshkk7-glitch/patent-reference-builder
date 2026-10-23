from contextlib import nullcontext
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.ops_environment import NAMES, save_user_values, status
from scripts.ops_client import TOKEN, request_bytes
from scripts.browser_session import CollectionError


def registry(initial=None, fail_write=None):
    values = dict(initial or {})
    writes = []
    def query(key, name):
        if name not in values: raise FileNotFoundError()
        return values[name]
    def write(key, name, reserved, kind, value):
        writes.append(name)
        if len(writes) == fail_write: raise OSError('simulated write failure')
        values[name] = value, kind
    def delete(key, name):
        if name not in values: raise FileNotFoundError()
        del values[name]
    api = SimpleNamespace(HKEY_CURRENT_USER=1, KEY_QUERY_VALUE=1, KEY_SET_VALUE=2,
        REG_SZ=1, REG_EXPAND_SZ=2, OpenKey=lambda *a:nullcontext(object()),
        CreateKeyEx=lambda *a:nullcontext(object()), QueryValueEx=query,
        SetValueEx=write, DeleteValue=delete, FlushKey=lambda key:None)
    return api, values, writes


class OpsEnvironment(unittest.TestCase):
    def test_status_only_reports_presence_and_distinguishes_restart_needed(self):
        api, values, _ = registry({NAMES[0]:('private-key',1),NAMES[1]:('private-secret',1)})
        with patch.dict('sys.modules',winreg=api), patch('sys.platform','win32'), patch.dict(os.environ,{},clear=True):
            result = status()
        self.assertEqual(result['process'],{name:False for name in NAMES})
        self.assertEqual(result['windows_user'],{name:True for name in NAMES})
        self.assertNotIn('private',json.dumps(result))

    def test_save_writes_only_two_named_values_and_keeps_other_settings(self):
        api, values, writes = registry({'Unrelated':('unchanged',2)})
        with patch.dict('sys.modules',winreg=api):
            save_user_values(('new-key','new-secret'))
        self.assertEqual(writes,list(NAMES))
        self.assertEqual(values['Unrelated'],('unchanged',2))
        self.assertEqual(values[NAMES[1]],('new-secret',1))

    def test_partial_write_failure_restores_existing_and_removes_new_value(self):
        for initial in ({NAMES[0]:('old-key',2),NAMES[1]:('old-secret',1)}, {}):
            api, values, _ = registry(initial,fail_write=2)
            with patch.dict('sys.modules',winreg=api):
                with self.assertRaises(OSError): save_user_values(('new-key','new-secret'))
            self.assertEqual(values,initial)

    def test_invalid_input_has_no_registry_mutation(self):
        api, values, writes = registry()
        for pair in (('', 'secret'),('key\nvalue','secret'),('key','비밀')):
            with patch.dict('sys.modules',winreg=api):
                with self.assertRaises(ValueError): save_user_values(pair)
        self.assertEqual(writes,[])

    def test_http_guidance_distinguishes_auth_permissions_and_quota_without_echo(self):
        for code, hint in ((400,'--setup'),(401,'--setup'),(403,'권한'),(429,'키를 교체하지'),(500,'서비스 상태')):
            error=HTTPError(TOKEN,code,'private-secret',{},io.BytesIO(b'private-key'))
            with patch('scripts.ops_client.build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(CollectionError) as caught:
                    request_bytes(TOKEN,{'Authorization':'private-secret'})
                message=str(caught.exception)
                self.assertIn(hint,message)
                self.assertNotIn('private',message)
                self.assertEqual(opener.return_value.open.call_count,1)
