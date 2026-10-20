"""Launch ordinary installed Chrome and attach locally, without changing security."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen


def chrome_executable():
    candidates = [shutil.which('google-chrome'), shutil.which('google-chrome-stable'),
                  shutil.which('chrome'), '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    for key in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        if os.environ.get(key):
            candidates.append(str(Path(os.environ[key])/'Google/Chrome/Application/chrome.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ValueError('설치된 Google Chrome을 찾지 못했습니다. --cdp로 준비된 로컬 Chrome에 연결하세요.')


@contextmanager
def native_chrome():
    executable = chrome_executable()
    with socket.socket() as address:
        address.bind(('127.0.0.1', 0))
        port = address.getsockname()[1]
    endpoint = f'http://127.0.0.1:{port}'
    # A task-only profile avoids attaching to or changing the user's daily profile.
    with tempfile.TemporaryDirectory(prefix='patent-chrome-', ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([executable, f'--remote-debugging-port={port}',
            '--remote-debugging-address=127.0.0.1', f'--user-data-dir={profile}',
            '--no-first-run', '--no-default-browser-check', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+15
            while True:
                try:
                    with urlopen(endpoint+'/json/version', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                exit_code = process.poll()
                if exit_code not in (None, 0):
                    raise RuntimeError(f'작업용 Chrome이 연결 준비 전에 비정상 종료했습니다 (종료 코드 {exit_code}).')
                if time.monotonic() >= deadline:
                    # A Chrome launcher can exit 0 while its browser child starts.
                    raise RuntimeError(f'작업용 Chrome의 로컬 연결 준비 시간 초과 (시작 프로세스 종료 코드 {exit_code}). '
                        '공식 특허 자료 누락과 별개의 브라우저 시작 오류입니다. --cdp 또는 --channel chrome --headed로 확인하세요.')
                time.sleep(.2)
            yield endpoint
        finally:
            # Stop only the process created above, never other Chrome processes.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
