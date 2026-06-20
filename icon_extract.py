"""
icon_extract.py
----------------
Pulls the icon embedded in a .exe (the same one Explorer/Steam would show)
using plain ctypes -- no pywin32 needed. The recipe:

  1. SHGetFileInfoW(..., SHGFI_ICON) -> an HICON for the file.
  2. DrawIconEx onto a memory device context sized to the icon.
  3. GetDIBits to pull the pixels out as a top-down 32-bit BGRA buffer.
  4. PIL.Image.frombuffer(..., "raw", "BGRA", ...) turns that into a normal
     RGBA image, which ImageTk can then turn into a Tkinter-displayable
     PhotoImage.

Results are cached by exe path (icons don't change at runtime) so the
profile list doesn't re-extract on every refresh.
"""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

SHGFI_ICON = 0x000000100
SHGFI_LARGEICON = 0x000000000
SHGFI_SMALLICON = 0x000000001
DI_NORMAL = 0x0003
BI_RGB = 0
DIB_RGB_COLORS = 0


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


try:
    shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    shell32.SHGetFileInfoW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW), wintypes.UINT, wintypes.UINT
    ]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.DrawIconEx.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON, ctypes.c_int, ctypes.c_int,
        wintypes.UINT, wintypes.HBRUSH, wintypes.UINT,
    ]
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ]
    _PROTOTYPES_OK = True
except Exception:
    logger.debug("Couldn't declare icon-extraction prototypes (non-Windows?)", exc_info=True)
    _PROTOTYPES_OK = False


def _extract_pil_image(exe_path, size=24):
    """Returns a PIL RGBA Image of the exe's icon, or None on any failure."""
    info = SHFILEINFOW()
    flags = SHGFI_ICON | (SHGFI_LARGEICON if size > 16 else SHGFI_SMALLICON)
    shell32.SHGetFileInfoW(exe_path, 0, ctypes.byref(info), ctypes.sizeof(info), flags)
    hicon = info.hIcon
    if not hicon:
        return None

    hdc = mem_dc = bmp = None
    try:
        hdc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, size, size)
        old_bmp = gdi32.SelectObject(mem_dc, bmp)

        user32.DrawIconEx(mem_dc, 0, 0, hicon, size, size, 0, None, DI_NORMAL)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size  # negative = top-down DIB (matches our raw "BGRA" read order)
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf = ctypes.create_string_buffer(size * size * 4)
        gdi32.GetDIBits(mem_dc, bmp, 0, size, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

        image = Image.frombuffer("RGBA", (size, size), buf.raw, "raw", "BGRA", 0, 1)
        gdi32.SelectObject(mem_dc, old_bmp)
        return image
    except Exception:
        logger.debug("Icon extraction failed for %s", exe_path, exc_info=True)
        return None
    finally:
        if bmp:
            gdi32.DeleteObject(bmp)
        if mem_dc:
            gdi32.DeleteDC(mem_dc)
        if hdc:
            user32.ReleaseDC(None, hdc)
        user32.DestroyIcon(hicon)


_cache = {}  # (exe_path, size) -> ImageTk.PhotoImage (or None if extraction failed)


def get_icon_photo(exe_path, size=24):
    """Returns a Tkinter-displayable PhotoImage for the given exe's icon,
    or None if it's unavailable (missing file, no PIL, extraction failure).
    Cached by path -- safe to call repeatedly while rendering a list."""
    if not exe_path or not PIL_AVAILABLE or not _PROTOTYPES_OK:
        return None
    key = (exe_path, size)
    if key in _cache:
        return _cache[key]
    photo = None
    try:
        image = _extract_pil_image(exe_path, size)
        if image is not None:
            photo = ImageTk.PhotoImage(image)
    except Exception:
        logger.debug("get_icon_photo failed for %s", exe_path, exc_info=True)
    _cache[key] = photo
    return photo


def clear_cache():
    _cache.clear()
