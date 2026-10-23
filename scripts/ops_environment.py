"""Inspect presence only, or save OPS user variables through a local masked GUI."""
import argparse
import json
import os
import sys

NAMES = ('EPO_OPS_KEY', 'EPO_OPS_SECRET')


def status():
    result = {'process': {name: bool(os.environ.get(name, '').strip()) for name in NAMES}}
    if sys.platform == 'win32':
        import winreg
        stored = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                for name in NAMES:
                    try:
                        value, kind = winreg.QueryValueEx(key, name)
                        stored[name] = kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and bool(str(value).strip())
                    except FileNotFoundError:
                        stored[name] = False
            result['windows_user'] = stored
        except FileNotFoundError:
            result['windows_user'] = {name: False for name in NAMES}
        except OSError:
            result['windows_user_status'] = 'unavailable'
    return result


def save_user_values(values):
    """Write only the two fixed names; restore previous values on partial failure."""
    import winreg
    if len(values) != 2 or not all(isinstance(value, str) and value and
            all(33 <= ord(c) <= 126 for c in value) for value in values):
        raise ValueError('두 영문·숫자 API 값을 공백·줄바꿈 없이 입력하세요.')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
        previous = {}
        for name in NAMES:
            try:
                previous[name] = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                previous[name] = None
        try:
            for name, value in zip(NAMES, values):
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.FlushKey(key)
            if not all(winreg.QueryValueEx(key, name) == (value, winreg.REG_SZ)
                       for name, value in zip(NAMES, values)):
                raise OSError('Environment verification failed')
        except Exception:
            for name, old in previous.items():
                if old is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, old[1], old[0])
            winreg.FlushKey(key)
            raise


def notify_environment_change():
    import ctypes
    from ctypes import wintypes
    send = ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                     wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    result = ctypes.c_size_t()
    text = ctypes.c_wchar_p('Environment')
    return bool(send(0xFFFF, 0x001A, 0, ctypes.cast(text, ctypes.c_void_p).value,
                     0x0002, 2000, ctypes.byref(result)))


def setup_gui():
    if sys.platform != 'win32':
        raise ValueError('이 저장 창은 Windows용입니다. EPO_OPS_KEY/EPO_OPS_SECRET을 운영체제 사용자 환경에 등록하세요.')
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('EPO OPS — 사용자 환경변수 설정')
    root.geometry('680x410')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='EPO API 키를 Windows 사용자 환경변수에 저장합니다.',
              font=('Malgun Gothic', 12)).pack(anchor='w')
    ttk.Label(frame, text='값은 채팅·TXT·로그에 기록하지 않습니다. 기존 값은 표시하지 않습니다.').pack(anchor='w', pady=(6,4))
    ttk.Label(frame, text='환경변수는 암호화 보관소가 아닙니다. 저장 후 Codex를 완전히 종료하고 다시 실행하세요.',
              wraplength=630).pack(anchor='w', pady=(0,15))
    entries = []
    for label in ('Consumer Key → EPO_OPS_KEY', 'Consumer Secret → EPO_OPS_SECRET'):
        ttk.Label(frame, text=label).pack(anchor='w')
        entry = ttk.Entry(frame, show='*', width=78)
        entry.pack(anchor='w', pady=(4,12))
        entries.append(entry)
    message = tk.StringVar(value='두 값을 입력한 뒤 저장하세요. 기존 두 환경변수가 있으면 교체합니다.')
    ttk.Label(frame, textvariable=message, wraplength=630).pack(anchor='w', pady=(0,12))

    def save():
        values = tuple(entry.get().strip() for entry in entries)
        try:
            save_user_values(values)
        except ValueError:
            message.set('두 API 값을 모두 입력하세요. 공백·줄바꿈·한글은 포함하지 마세요.')
            return
        except Exception:
            message.set('저장을 완료하지 못했습니다. 키 값 없이 저장 실패라고 알려주세요.')
            return
        for entry in entries:
            entry.delete(0, 'end')
            entry.configure(state='disabled')
        button.configure(state='disabled')
        try:
            notify_environment_change()
        except OSError:
            pass  # Registry writes succeeded; restarting remains necessary.
        message.set('저장 완료. 창을 닫고 Codex를 완전히 종료한 뒤 다시 실행하세요.')

    button = ttk.Button(frame, text='Windows 사용자 환경변수에 저장', command=save)
    button.pack(anchor='w')
    entries[0].focus_set()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='OPS 환경변수 존재 여부 확인 또는 로컬 숨김 입력 설정')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--status', action='store_true', help='실제 값 없이 설정 여부만 출력')
    group.add_argument('--setup', action='store_true', help='Windows 사용자 환경변수 등록/교체 창')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(), ensure_ascii=False))
    else:
        setup_gui()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('OPS 환경변수 도우미 실행 실패. 키 값을 보내지 말고 로컬 설정 안내를 확인하세요.', file=sys.stderr)
        sys.exit(2)
