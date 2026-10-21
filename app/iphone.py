"""Acesso ao iPhone pelo Shell do Windows (MTP): listar, miniatura, copiar, apagar.

Tudo anda por PIDL (lista de bytes do pywin32): é dado puro, passa entre threads, e é o único
caminho que o MTP aceita — o texto de FolderItem.Path não abre com SHCreateItemFromParsingName.
"""
import os
import re
import pythoncom
from win32com.shell import shell, shellcon
from win32com.propsys import pscon

NOME_APARELHO = "Apple iPhone"
_desk = None


def com():
    """Chamar no começo de toda thread que usa o Shell."""
    pythoncom.CoInitialize()


def _filhos(pasta):
    flags = shellcon.SHCONTF_FOLDERS | shellcon.SHCONTF_NONFOLDERS
    enum = pasta.EnumObjects(0, flags)
    if enum is None:
        return
    for pidl in enum:
        yield pidl, pasta.GetDisplayNameOf(pidl, shellcon.SHGDN_NORMAL)


def _bind(pidl):
    return shell.SHGetDesktopFolder().BindToObject(pidl, None, shell.IID_IShellFolder)


def localizar():
    """PIDL do armazenamento interno do iPhone, ou None se não estiver conectado/desbloqueado."""
    pc_pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DRIVES)
    for p, nome in _filhos(_bind(pc_pidl)):
        if nome == NOME_APARELHO:
            ph_pidl = pc_pidl + p
            for s, _ in _filhos(_bind(ph_pidl)):
                return ph_pidl + s
            return None  # aparelho aparece, mas bloqueado / sem "Confiar"
    return None


def espaco():
    """(capacidade, livre) em bytes do armazenamento do iPhone, ou None."""
    raiz = localizar()
    if raiz is None:
        return None
    it = shell.SHCreateItemFromIDList(raiz, shell.IID_IShellItem2)
    try:
        return int(it.GetProperty(pscon.PKEY_Capacity)), int(it.GetProperty(pscon.PKEY_FreeSpace))
    except Exception:
        return None


def _data(item):
    for chave in (pscon.PKEY_Photo_DateTaken, pscon.PKEY_DateCreated, pscon.PKEY_DateModified):
        try:
            v = item.GetProperty(chave)  # pywin32 já devolve datetime (UTC) ou None
            if v:
                if v.tzinfo is not None:
                    v = v.astimezone()
                return v.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return ""


def listar(progresso=None):
    """Lista todos os arquivos das pastas do iPhone. Devolve lista de dicts."""
    raiz = localizar()
    if raiz is None:
        return None
    arquivos = []
    pastas = list(_filhos(_bind(raiz)))
    for n, (p, nome_pasta) in enumerate(pastas, 1):
        if progresso:
            progresso(f"Lendo {nome_pasta} ({n}/{len(pastas)})")
        pasta_pidl = raiz + p
        for fp, _ in _filhos(_bind(pasta_pidl)):
            pidl = pasta_pidl + fp
            item = shell.SHCreateItemFromIDList(pidl, shell.IID_IShellItem2)
            try:
                nome = item.GetString(pscon.PKEY_FileName)
            except Exception:
                nome = item.GetDisplayName(shellcon.SIGDN_NORMALDISPLAY)
            try:
                tam = int(item.GetUInt64(pscon.PKEY_Size))
            except Exception:
                tam = 0
            arquivos.append({"pasta": nome_pasta, "nome": nome, "bytes": tam, "data": _data(item), "pidl": pidl})
    return arquivos


def nomes_na_pasta(nome_pasta):
    """Nomes (com extensão) que existem hoje numa pasta do iPhone — para confirmar exclusão."""
    raiz = localizar()
    if raiz is None:
        return None
    for p, nome in _filhos(_bind(raiz)):
        if nome == nome_pasta:
            pasta_pidl = raiz + p
            out = set()
            for fp, _ in _filhos(_bind(pasta_pidl)):
                it = shell.SHCreateItemFromIDList(pasta_pidl + fp, shell.IID_IShellItem2)
                out.add(it.GetString(pscon.PKEY_FileName))
            return out
    return set()


def _operacao():
    op = pythoncom.CoCreateInstance(shell.CLSID_FileOperation, None, pythoncom.CLSCTX_ALL, shell.IID_IFileOperation)
    op.SetOperationFlags(shellcon.FOF_NOCONFIRMATION | shellcon.FOF_SILENT | shellcon.FOF_NOERRORUI
                         | shellcon.FOFX_EARLYFAILURE | shellcon.FOF_NOCONFIRMMKDIR)
    return op


def _item_conferido(a):
    """ShellItem do arquivo `a`, só se o PIDL ainda aponta para o mesmo nome e tamanho.

    O PIDL do MTP carrega o identificador do objeto no aparelho; se o iPhone for reconectado,
    ele pode passar a apontar para outro arquivo. Nada é copiado ou apagado sem esta conferência."""
    it = shell.SHCreateItemFromIDList(a["pidl"], shell.IID_IShellItem2)
    nome = it.GetString(pscon.PKEY_FileName)
    tam = int(it.GetUInt64(pscon.PKEY_Size))
    if nome != a["nome"] or tam != a["bytes"]:
        raise RuntimeError(f"o iPhone mudou desde a leitura ({a['nome']} virou {nome}); use 'Ler iPhone de novo'")
    return it


def copiar(a, pasta_destino):
    """Copia o arquivo `a` do iPhone para uma pasta do PC (que precisa existir). Síncrono."""
    op = _operacao()
    src = _item_conferido(a)
    dst = shell.SHCreateItemFromParsingName(os.path.abspath(pasta_destino), None, shell.IID_IShellItem)
    op.CopyItem(src, dst, None, None)
    op.PerformOperations()
    if op.GetAnyOperationsAborted():
        raise RuntimeError("cópia interrompida")


def apagar(arquivos):
    """Apaga arquivos do iPhone. Definitivo: não passa por 'Apagados recentemente'.
    Confere todos antes; se um não bater, não apaga nenhum do lote."""
    itens = [_item_conferido(a) for a in arquivos]
    op = _operacao()
    for it in itens:
        op.DeleteItem(it, None)
    op.PerformOperations()
    if op.GetAnyOperationsAborted():
        raise RuntimeError("exclusão interrompida")


# --- agrupamento: uma foto do iPhone = vários arquivos -------------------------------------
_RE_IMG = re.compile(r"^(IMG)_[EO]?(\d+)$", re.I)
FOTO = {".heic", ".jpg", ".jpeg", ".png", ".gif", ".dng", ".webp", ".tif", ".tiff"}
VIDEO = {".mov", ".mp4", ".m4v", ".avi", ".3gp"}


def chave_grupo(nome):
    base, _ = os.path.splitext(nome)
    m = _RE_IMG.match(base)
    return f"IMG_{m.group(2)}" if m else base


def tipo(nome):
    ext = os.path.splitext(nome)[1].lower()
    return "foto" if ext in FOTO else "video" if ext in VIDEO else "outro"


def capa(arquivos):
    """Arquivo que dá a miniatura do grupo: editada > foto > vídeo > qualquer um."""
    def peso(a):
        base = os.path.splitext(a["nome"])[0].upper()
        t = tipo(a["nome"])
        editada = base.startswith("IMG_E")
        return (t == "foto" and editada, t == "foto", t == "video" and editada, t == "video")
    return max(arquivos, key=peso)


def video(arquivos):
    """Vídeo do grupo para tocar: o editado se houver, senão o original."""
    vs = [a for a in arquivos if tipo(a["nome"]) == "video"]
    return max(vs, key=lambda a: os.path.splitext(a["nome"])[0].upper().startswith("IMG_E"))
