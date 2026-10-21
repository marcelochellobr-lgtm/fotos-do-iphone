"""Janela padrão do Windows para escolher uma pasta (a mesma do "Abrir" de qualquer programa).

Roda como processo à parte: python escolher_pasta.py "<pasta inicial>"  → imprime a pasta escolhida
(ou nada, se cancelar). À parte porque a janela precisa de uma thread de interface própria.
"""
import ctypes
import sys
from ctypes import POINTER, byref, c_void_p, c_uint, wintypes

import comtypes
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown


class IShellItem(IUnknown):
    _iid_ = GUID("{43826d1e-e718-42ee-bc55-a1e261c37bfe}")
    _methods_ = [
        COMMETHOD([], HRESULT, "BindToHandler", (["in"], c_void_p), (["in"], POINTER(GUID)), (["in"], POINTER(GUID)), (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "GetParent", (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "GetDisplayName", (["in"], c_uint, "sigdn"), (["out"], POINTER(ctypes.c_void_p), "nome")),
        COMMETHOD([], HRESULT, "GetAttributes", (["in"], c_uint), (["out"], POINTER(c_uint))),
        COMMETHOD([], HRESULT, "Compare", (["in"], c_void_p), (["in"], c_uint), (["out"], POINTER(ctypes.c_int))),
    ]


# IFileOpenDialog herda IFileDialog, que herda IModalWindow: os métodos vêm nesta ordem exata.
class IFileOpenDialog(IUnknown):
    _iid_ = GUID("{d57c7288-d4ad-4768-be02-9d969532d960}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Show", (["in"], wintypes.HWND)),
        COMMETHOD([], HRESULT, "SetFileTypes", (["in"], c_uint), (["in"], c_void_p)),
        COMMETHOD([], HRESULT, "SetFileTypeIndex", (["in"], c_uint)),
        COMMETHOD([], HRESULT, "GetFileTypeIndex", (["out"], POINTER(c_uint))),
        COMMETHOD([], HRESULT, "Advise", (["in"], c_void_p), (["out"], POINTER(wintypes.DWORD))),
        COMMETHOD([], HRESULT, "Unadvise", (["in"], wintypes.DWORD)),
        COMMETHOD([], HRESULT, "SetOptions", (["in"], c_uint)),
        COMMETHOD([], HRESULT, "GetOptions", (["out"], POINTER(c_uint))),
        COMMETHOD([], HRESULT, "SetDefaultFolder", (["in"], POINTER(IShellItem))),
        COMMETHOD([], HRESULT, "SetFolder", (["in"], POINTER(IShellItem))),
        COMMETHOD([], HRESULT, "GetFolder", (["out"], POINTER(POINTER(IShellItem)))),
        COMMETHOD([], HRESULT, "GetCurrentSelection", (["out"], POINTER(POINTER(IShellItem)))),
        COMMETHOD([], HRESULT, "SetFileName", (["in"], wintypes.LPCWSTR)),
        COMMETHOD([], HRESULT, "GetFileName", (["out"], POINTER(wintypes.LPWSTR))),
        COMMETHOD([], HRESULT, "SetTitle", (["in"], wintypes.LPCWSTR)),
        COMMETHOD([], HRESULT, "SetOkButtonLabel", (["in"], wintypes.LPCWSTR)),
        COMMETHOD([], HRESULT, "SetFileNameLabel", (["in"], wintypes.LPCWSTR)),
        COMMETHOD([], HRESULT, "GetResult", (["out"], POINTER(POINTER(IShellItem)))),
    ]


CLSID_FileOpenDialog = GUID("{DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7}")
FOS_PICKFOLDERS = 0x20
FOS_FORCEFILESYSTEM = 0x40
SIGDN_FILESYSPATH = 0x80058000
ERRO_CANCELADO = -2147023673  # HRESULT_FROM_WIN32(ERROR_CANCELLED)


def escolher(inicial=""):
    comtypes.CoInitialize()
    dlg = comtypes.CoCreateInstance(CLSID_FileOpenDialog, interface=IFileOpenDialog)
    dlg.SetOptions(dlg.GetOptions() | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)
    dlg.SetTitle("Escolha a pasta")
    dlg.SetOkButtonLabel("Usar esta pasta")
    if inicial:
        shell32 = ctypes.windll.shell32
        shell32.SHCreateItemFromParsingName.argtypes = [wintypes.LPCWSTR, c_void_p, POINTER(GUID), POINTER(c_void_p)]
        p = c_void_p()
        if shell32.SHCreateItemFromParsingName(inicial, None, byref(IShellItem._iid_), byref(p)) == 0 and p:
            dlg.SetFolder(ctypes.cast(p, POINTER(IShellItem)))
    # Dono = a janela que estava na frente (o navegador): a caixa abre por cima dela.
    dono = ctypes.windll.user32.GetForegroundWindow()
    try:
        dlg.Show(dono)
    except comtypes.COMError as e:
        if e.hresult == ERRO_CANCELADO:
            return ""
        raise
    ptr = dlg.GetResult().GetDisplayName(SIGDN_FILESYSPATH)
    caminho = ctypes.wstring_at(ptr)
    ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(ptr))
    return caminho


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(escolher(sys.argv[1] if len(sys.argv) > 1 else ""))
