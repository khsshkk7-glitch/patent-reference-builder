"""Resolve the user's configured Downloads folder without hard-coded accounts."""
import os
from pathlib import Path
import shlex
import sys


def windows_downloads():
    import ctypes
    from ctypes import wintypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    folder = GUID.from_buffer_copy(uuid.UUID('374de290-123f-4565-9164-39c4925e467b').bytes_le)
    value = ctypes.c_wchar_p()
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD,
                                          wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    result = shell.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(value))
    try:
        if result != 0 or not value.value:
            raise OSError(f'다운로드 폴더 위치 확인 실패 (HRESULT {result:#x})')
        return Path(value.value)
    finally:
        if value:
            ole.CoTaskMemFree(ctypes.cast(value, ctypes.c_void_p))


def downloads_directory():
    if sys.platform == 'win32':
        # A failed lookup must not silently save into a wrong, unredirected folder.
        return windows_downloads()
    home = Path.home()
    if sys.platform.startswith('linux'):
        config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'user-dirs.dirs'
        if config.is_file():
            for line in config.read_text(encoding='utf-8').splitlines():
                key, sep, value = line.strip().partition('=')
                if sep and key.strip() == 'XDG_DOWNLOAD_DIR':
                    parts = shlex.split(value, comments=True)
                    if len(parts) == 1:
                        path = Path(parts[0].replace('${HOME}', str(home)).replace('$HOME', str(home)))
                        if path.is_absolute():
                            return path
    return home / 'Downloads'


def output_directory(explicit=None):
    return (Path(explicit).expanduser() if explicit is not None else downloads_directory()).resolve()
