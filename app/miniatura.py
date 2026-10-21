"""Miniatura de um item do Shell (inclusive do iPhone via MTP) pelo IShellItemImageFactory."""
import ctypes
from ctypes import wintypes, byref, POINTER, c_void_p
import comtypes
from comtypes import GUID, HRESULT, COMMETHOD
from PIL import Image


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class IShellItemImageFactory(comtypes.IUnknown):
    _iid_ = GUID("{bcc18b79-ba16-442f-80c4-8a59c30c463b}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetImage",
                  (["in"], SIZE, "size"),
                  (["in"], ctypes.c_int, "flags"),
                  (["out"], POINTER(wintypes.HBITMAP), "phbm")),
    ]


_shell32 = ctypes.windll.shell32
_shell32.SHCreateItemFromIDList.argtypes = [ctypes.c_char_p, POINTER(GUID), POINTER(c_void_p)]
_shell32.SHCreateItemFromIDList.restype = HRESULT
_gdi32 = ctypes.windll.gdi32
_user32 = ctypes.windll.user32
_gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, c_void_p]
_gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, c_void_p, c_void_p, wintypes.UINT]
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]


class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long),
                ("bmWidthBytes", ctypes.c_long), ("bmPlanes", wintypes.WORD),
                ("bmBitsPixel", wintypes.WORD), ("bmBits", c_void_p)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


SIIGBF_RESIZETOFIT = 0x0
SIIGBF_BIGGERSIZEOK = 0x1
SIIGBF_THUMBNAILONLY = 0x8


def miniatura_de_arquivo(caminho, lado):
    """Mesma coisa para um arquivo no PC — serve para o Windows converter HEIC em imagem comum."""
    from win32com.shell import shell
    pidl, _ = shell.SHParseDisplayName(caminho, 0)
    return miniatura(shell.PIDLAsString(pidl), lado)


def miniatura(pidl_bytes, lado=256):
    """Recebe o PIDL absoluto em bytes (shell.PIDLAsString). Devolve PIL.Image, ou None sem miniatura.

    Pelo caminho de texto (FolderItem.Path) o MTP do iPhone não abre — só pelo PIDL."""
    ptr = c_void_p()
    try:
        _shell32.SHCreateItemFromIDList(pidl_bytes, byref(IShellItemImageFactory._iid_), byref(ptr))
    except OSError:
        return None
    if not ptr:
        return None
    fab = ctypes.cast(ptr, POINTER(IShellItemImageFactory))
    try:
        hbm = fab.GetImage(SIZE(lado, lado), SIIGBF_BIGGERSIZEOK | SIIGBF_THUMBNAILONLY)
    except (comtypes.COMError, OSError):
        return None
    try:
        bm = BITMAP()
        _gdi32.GetObjectW(hbm, ctypes.sizeof(bm), byref(bm))
        w, h = bm.bmWidth, bm.bmHeight
        info = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h,
                                biPlanes=1, biBitCount=32, biCompression=0)
        buf = ctypes.create_string_buffer(w * h * 4)
        hdc = _user32.GetDC(None)
        _gdi32.GetDIBits(hdc, hbm, 0, h, buf, byref(info), 0)
        _user32.ReleaseDC(None, hdc)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
        img.thumbnail((lado, lado))
        return img
    finally:
        _gdi32.DeleteObject(hbm)
