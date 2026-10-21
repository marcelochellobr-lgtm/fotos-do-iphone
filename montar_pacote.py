"""Monta o pacote de distribuição: dist/Fotos-do-iPhone-v<versão>.zip

Roda no computador de quem publica (precisa de internet aqui, uma vez). Quem baixa o .zip
recebe tudo pronto e não precisa de internet para instalar nem para usar.

    python montar_pacote.py

O que entra na pasta "Fotos do iPhone":
  python/   Python oficial, versão portátil (python.org), com as bibliotecas abaixo já dentro
  app/      o código do app (texto)
  Abrir Fotos do iPhone.bat, Criar atalho na Area de Trabalho.bat, LEIA-ME.txt, LICENSE
"""
import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

VERSAO = "1.0.1"
PYTHON = "3.13.3"
# Versões fixas: o pacote sai sempre igual, e qualquer um pode conferir o que vai dentro.
BIBLIOTECAS = [
    "Flask==3.1.3", "Werkzeug==3.1.9", "Jinja2==3.1.6", "MarkupSafe==3.0.4", "itsdangerous==2.2.0",
    "click==8.5.0", "blinker==1.9.0",
    "pywin32==312", "comtypes==1.4.17", "pillow==13.0.0",
]

AQUI = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(AQUI, "dist")
PASTA = os.path.join(DIST, "Fotos do iPhone")


def passo(msg):
    print(f"\n== {msg}")


def main():
    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(PASTA)

    passo(f"Python {PYTHON} portátil, direto do python.org")
    url = f"https://www.python.org/ftp/python/{PYTHON}/python-{PYTHON}-embed-amd64.zip"
    dados = urllib.request.urlopen(url).read()
    py = os.path.join(PASTA, "python")
    zipfile.ZipFile(io.BytesIO(dados)).extractall(py)

    passo("Conferindo a assinatura digital do python.exe")
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"$s=Get-AuthenticodeSignature '{os.path.join(py, 'python.exe')}'; "
                          "$s.Status; $s.SignerCertificate.Subject"], capture_output=True, text=True)
    print(out.stdout.strip())
    if not out.stdout.startswith("Valid"):
        sys.exit("assinatura do python.exe não confere — parei")

    passo("Liberando a pasta de bibliotecas no Python portátil")
    pth = os.path.join(py, f"python{PYTHON.replace('.', '')[:3]}._pth")
    linhas = open(pth, encoding="utf-8").read().splitlines()
    linhas = [("import site" if l.strip() == "#import site" else l) for l in linhas]
    linhas.insert(-1, r"Lib\site-packages")
    open(pth, "w", encoding="utf-8").write("\n".join(linhas) + "\n")

    passo("Bibliotecas (só pacotes prontos para Windows 64 bits, sem compilar nada)")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps",
                    "--target", os.path.join(py, "Lib", "site-packages"),
                    "--only-binary=:all:", "--platform", "win_amd64",
                    "--python-version", PYTHON.rsplit(".", 1)[0], "--implementation", "cp",
                    *BIBLIOTECAS], check=True)

    passo("Tirando exemplos, testes e arquivos de cache das bibliotecas (não servem ao app)")
    sp = os.path.join(py, "Lib", "site-packages")
    for raiz, dirs, _ in os.walk(sp, topdown=False):
        for d in dirs:
            if d in ("__pycache__", "demos", "Demos", "test", "tests"):
                shutil.rmtree(os.path.join(raiz, d), ignore_errors=True)

    passo("App e arquivos de apoio")
    shutil.copytree(os.path.join(AQUI, "app"), os.path.join(PASTA, "app"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("Abrir Fotos do iPhone.bat", "Criar atalho na Area de Trabalho.bat", "LEIA-ME.txt", "LICENSE"):
        shutil.copy2(os.path.join(AQUI, f), PASTA)

    passo("Compactando")
    destino = os.path.join(DIST, f"Fotos-do-iPhone-v{VERSAO}.zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for raiz, _, nomes in os.walk(PASTA):
            for n in nomes:
                p = os.path.join(raiz, n)
                z.write(p, os.path.relpath(p, DIST))
    print(f"{destino}  ({os.path.getsize(destino) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
