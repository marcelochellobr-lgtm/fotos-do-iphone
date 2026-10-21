"""Fotos do iPhone — servidor local que a tela no navegador usa.

Só escuta em 127.0.0.1: o endereço que existe apenas dentro deste computador. Não fala com a
internet, nem com outros aparelhos da rede.

Regra de ouro: só se apaga do iPhone o que tem cópia no PC conferida por nome + tamanho exato,
e a conferência é refeita no instante da exclusão.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import threading
import webbrowser
from collections import defaultdict
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)  # o Python portátil não acrescenta a pasta do script sozinho

from flask import Flask, jsonify, request, send_file, Response  # noqa: E402

import iphone  # noqa: E402
from miniatura import miniatura, miniatura_de_arquivo  # noqa: E402

# Tudo o que o app grava fica em "dados", ao lado da pasta "app". Apagar a pasta do app apaga tudo.
DADOS = os.path.join(os.path.dirname(AQUI), "dados")
os.makedirs(DADOS, exist_ok=True)
REGISTRO = os.path.join(DADOS, "registro.json")     # "pasta|nome|bytes" -> {"pc": caminho, "em": data}
APAGADOS = os.path.join(DADOS, "apagados.csv")      # histórico do que saiu do iPhone
ESPACO = os.path.join(DADOS, "espaco.json")         # livre informado + o que se apagou desde então
CACHE = os.path.join(DADOS, "cache")
PORTA = int(os.environ.get("FOTOS_IPHONE_PORTA", "8150"))

app = Flask(__name__, static_folder=None)
trava_reg = threading.Lock()
estado = {"arquivos": [], "conectado": False, "lido_em": None, "espaco": None}
tarefa = {"nome": None, "msg": "", "feito": 0, "total": 0, "erro": None, "rodando": False, "resultado": None}
trava_tarefa = threading.Lock()
sem_mini = threading.Semaphore(3)


# --- registro de cópias conferidas ---------------------------------------------------------
def chave(a):
    return f"{a['pasta']}|{a['nome']}|{a['bytes']}"


def ler_registro():
    try:
        with open(REGISTRO, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def gravar_registro(reg):
    tmp = REGISTRO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=0)
    os.replace(tmp, REGISTRO)


def registrar(pares):
    """pares: lista de (arquivo_iphone, caminho_no_pc)."""
    with trava_reg:
        reg = ler_registro()
        agora = datetime.now().isoformat(timespec="seconds")
        for a, pc in pares:
            reg[chave(a)] = {"pc": pc, "em": agora}
        gravar_registro(reg)


def copia_ok(a, reg):
    """Caminho da cópia no PC se ela existe com o mesmo tamanho; senão None."""
    r = reg.get(chave(a))
    if not r:
        return None
    try:
        return r["pc"] if os.path.getsize(r["pc"]) == a["bytes"] else None
    except OSError:
        return None


# --- espaço livre --------------------------------------------------------------------------
# O iPhone informa o espaço livre da hora em que o cabo foi conectado e não atualiza depois de
# apagar (nem pelo Shell, nem perguntando direto pelo WPD). Então: livre = informado + o que o app
# apagou desde então. Quando o número informado muda (reconexão), a soma zera.
def _ler_json_espaco():
    try:
        with open(ESPACO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def atualizar_espaco(apagou=0):
    salvo = _ler_json_espaco()
    lido = iphone.espaco()
    if lido is None:
        return
    cap, informado = lido
    soma = salvo.get("apagado", 0) if salvo.get("livre_informado") == informado else 0
    soma += apagou
    with open(ESPACO, "w", encoding="utf-8") as f:
        json.dump({"livre_informado": informado, "apagado": soma}, f)
    estado["espaco"] = {"total": cap, "livre": min(cap, informado + soma), "estimado": soma > 0}


# --- tarefas em segundo plano --------------------------------------------------------------
def rodar(nome, fn, *args):
    with trava_tarefa:
        if tarefa["rodando"]:
            return False
        tarefa.update(nome=nome, msg="Começando…", feito=0, total=0, erro=None, rodando=True, resultado=None)

    def alvo():
        iphone.com()
        try:
            tarefa["resultado"] = fn(*args)
        except Exception as e:
            tarefa["erro"] = str(e)
        finally:
            tarefa["rodando"] = False

    threading.Thread(target=alvo, daemon=True).start()
    return True


def t_ler():
    arqs = iphone.listar(lambda m: tarefa.update(msg=m))
    if arqs is None:
        estado.update(arquivos=[], conectado=False)
        raise RuntimeError("iPhone não encontrado. Conecte o cabo, desbloqueie o aparelho e toque em "
                           "'Confiar'. Se ele não aparece no Explorador de Arquivos, instale o app "
                           "gratuito 'Apple Devices' da Microsoft Store e conecte de novo.")
    # id fixo pelo conteúdo, nunca pela ordem: o navegador guarda miniatura por id, e a ordem
    # muda quando algo é apagado — com id por posição, a miniatura de um aparecia no outro.
    for a in arqs:
        a["id"] = hashlib.sha1(chave(a).encode()).hexdigest()[:12]
    estado.update(arquivos=arqs, conectado=True, lido_em=datetime.now().isoformat(timespec="seconds"))
    atualizar_espaco()
    return {"arquivos": len(arqs)}


def t_copiar(ids, destino):
    por_id = {a["id"]: a for a in estado["arquivos"]}
    arqs = [por_id[i] for i in ids if i in por_id]
    tarefa.update(total=len(arqs))
    feitos, pulados, erros = 0, 0, []
    for n, a in enumerate(arqs, 1):
        tarefa.update(feito=n - 1, msg=f"Copiando {a['nome']} ({n}/{len(arqs)})")
        pasta = os.path.join(destino, a["pasta"])
        final = os.path.join(pasta, a["nome"])
        try:
            os.makedirs(pasta, exist_ok=True)
            if os.path.isfile(final) and os.path.getsize(final) == a["bytes"]:
                registrar([(a, final)])
                pulados += 1
                continue
            tmp_dir = os.path.join(pasta, ".copiando")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp = os.path.join(tmp_dir, a["nome"])
            if os.path.exists(tmp):
                os.remove(tmp)
            iphone.copiar(a, tmp_dir)
            if not os.path.isfile(tmp) or os.path.getsize(tmp) != a["bytes"]:
                raise RuntimeError("tamanho diferente depois da cópia")
            if os.path.exists(final):  # mesmo nome, outro conteúdo: não sobrescreve
                base, ext = os.path.splitext(a["nome"])
                k = 2
                while os.path.exists(os.path.join(pasta, f"{base} ({k}){ext}")):
                    k += 1
                final = os.path.join(pasta, f"{base} ({k}){ext}")
            os.replace(tmp, final)
            registrar([(a, final)])
            feitos += 1
        except Exception as e:
            erros.append(f"{a['pasta']}/{a['nome']}: {e}")
    for pasta in {os.path.join(destino, a["pasta"], ".copiando") for a in arqs}:
        try:
            os.rmdir(pasta)
        except OSError:
            pass
    tarefa.update(feito=len(arqs), msg="Cópia terminada")
    return {"copiados": feitos, "ja_estavam": pulados, "erros": erros}


def t_apagar(ids):
    por_id = {a["id"]: a for a in estado["arquivos"]}
    arqs = [por_id[i] for i in ids if i in por_id]
    reg = ler_registro()
    # Conferência no instante da exclusão: qualquer arquivo sem cópia boa fica.
    liberados = [(a, copia_ok(a, reg)) for a in arqs]
    recusados = [f"{a['pasta']}/{a['nome']}" for a, pc in liberados if not pc]
    liberados = [(a, pc) for a, pc in liberados if pc]
    tarefa.update(total=len(liberados))
    por_pasta = defaultdict(list)
    for a, pc in liberados:
        por_pasta[a["pasta"]].append((a, pc))
    apagados, falhas, n = [], [], 0
    novo_log = not os.path.exists(APAGADOS)
    with open(APAGADOS, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if novo_log:
            w.writerow(["apagado_em", "pasta_iphone", "arquivo", "bytes", "copia_no_pc"])
        for pasta, itens in por_pasta.items():
            for i in range(0, len(itens), 25):
                lote = itens[i:i + 25]
                n += len(lote)
                tarefa.update(feito=n, msg=f"Apagando em {pasta} ({n}/{len(liberados)})")
                try:
                    iphone.apagar([a for a, _ in lote])
                except Exception as e:
                    falhas.append(f"{pasta}: {e}")
            restam = iphone.nomes_na_pasta(pasta) or set()
            agora = datetime.now().isoformat(timespec="seconds")
            for a, pc in itens:
                if a["nome"] in restam:
                    falhas.append(f"{pasta}/{a['nome']}: continua no iPhone")
                else:
                    apagados.append(a)
                    w.writerow([agora, pasta, a["nome"], a["bytes"], pc])
    sumiram = {a["id"] for a in apagados}
    estado["arquivos"] = [a for a in estado["arquivos"] if a["id"] not in sumiram]
    atualizar_espaco(apagou=sum(a["bytes"] for a in apagados))
    tarefa.update(msg="Exclusão terminada")
    return {"apagados": len(apagados), "bytes": sum(a["bytes"] for a in apagados),
            "recusados": recusados, "erros": falhas}


def t_conferir(pasta_pc):
    """Procura no PC (recursivo) cópias com mesmo nome e tamanho dos arquivos do iPhone."""
    tarefa.update(msg=f"Lendo {pasta_pc}…")
    indice = defaultdict(list)
    for raiz, dirs, nomes in os.walk(pasta_pc):
        dirs[:] = [d for d in dirs if d != ".copiando"]
        for nm in nomes:
            p = os.path.join(raiz, nm)
            try:
                indice[(nm.lower(), os.path.getsize(p))].append(p)
            except OSError:
                pass
    pares = []
    for a in estado["arquivos"]:
        achados = indice.get((a["nome"].lower(), a["bytes"]))
        if achados:
            mesma_pasta = [p for p in achados if os.path.basename(os.path.dirname(p)) == a["pasta"]]
            pares.append((a, (mesma_pasta or achados)[0]))
    registrar(pares)
    return {"conferidos": len(pares)}


# --- rotas ---------------------------------------------------------------------------------
@app.before_request
def _com():
    iphone.com()


@app.get("/")
def index():
    return send_file(os.path.join(AQUI, "index.html"))


@app.get("/favicon.ico")
def favicon():
    return send_file(os.path.join(AQUI, "icone.ico"), mimetype="image/x-icon", max_age=86400)


@app.get("/api/estado")
def api_estado():
    return jsonify(tarefa=tarefa, conectado=estado["conectado"], lido_em=estado["lido_em"])


@app.get("/api/itens")
def api_itens():
    reg = ler_registro()
    grupos = defaultdict(list)
    for a in estado["arquivos"]:
        grupos[(a["pasta"], iphone.chave_grupo(a["nome"]))].append(a)
    saida = []
    for (pasta, k), arqs in grupos.items():
        arqs.sort(key=lambda a: a["nome"])
        info = []
        for a in arqs:
            info.append({"id": a["id"], "nome": a["nome"], "bytes": a["bytes"], "pc": copia_ok(a, reg)})
        n_ok = sum(1 for i in info if i["pc"])
        tipos = {iphone.tipo(a["nome"]) for a in arqs}
        saida.append({
            "id": f"{pasta}|{k}", "pasta": pasta, "nome": k,
            "data": min((a["data"] for a in arqs if a["data"]), default=""),
            "bytes": sum(a["bytes"] for a in arqs),
            "tipo": "video" if tipos == {"video"} or ("video" in tipos and "foto" not in tipos) else "foto",
            "live": "foto" in tipos and "video" in tipos,
            "editada": any(os.path.splitext(a["nome"])[0].upper().startswith("IMG_E") for a in arqs),
            "status": "pc" if n_ok == len(info) else "parcial" if n_ok else "iphone",
            "capa": iphone.capa(arqs)["id"], "arquivos": info,
            "video": iphone.video(arqs)["id"] if "video" in tipos else None,
        })
    saida.sort(key=lambda g: (g["pasta"], g["data"], g["nome"]), reverse=True)
    return jsonify(itens=saida, conectado=estado["conectado"], lido_em=estado["lido_em"],
                   espaco=estado["espaco"])


_PLACEHOLDER = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" '
                'fill="#2a2a2e"/><text x="50" y="56" font-size="14" text-anchor="middle" fill="#888" '
                'font-family="sans-serif">{}</text></svg>')


@app.get("/mini/<fid>")
def mini(fid):
    lado = 800 if request.args.get("grande") else 320
    a = _arquivo(fid)
    if a is None:
        return Response(_PLACEHOLDER.format("?"), mimetype="image/svg+xml")
    os.makedirs(CACHE, exist_ok=True)
    h = hashlib.sha1(f"{chave(a)}|{lado}".encode()).hexdigest()
    arq = os.path.join(CACHE, h + ".jpg")
    if not os.path.exists(arq):
        with sem_mini:
            img = miniatura(iphone.shell.PIDLAsString(a["pidl"]), lado)
        if img is None:
            ext = os.path.splitext(a["nome"])[1].upper().lstrip(".")
            return Response(_PLACEHOLDER.format(ext), mimetype="image/svg+xml")
        img.save(arq, quality=82)
    r = send_file(arq, mimetype="image/jpeg")
    r.headers["Cache-Control"] = "max-age=86400"
    return r


# --- original em resolução cheia (ver foto grande / tocar vídeo) -------------------------
ORIGINAIS = os.path.join(CACHE, "originais")   # cópias temporárias do que só está no iPhone
LIMITE_ORIGINAIS = 3e9                          # passa disso, apaga as mais antigas
_travas_arq = defaultdict(threading.Lock)


def _limpar_originais():
    arqs = []
    for raiz, _, nomes in os.walk(ORIGINAIS):
        for nm in nomes:
            p = os.path.join(raiz, nm)
            arqs.append((os.path.getmtime(p), os.path.getsize(p), p))
    total = sum(t for _, t, _ in arqs)
    for _, t, p in sorted(arqs):
        if total <= LIMITE_ORIGINAIS:
            break
        try:
            os.remove(p)
            total -= t
        except OSError:
            pass


def caminho_local(a):
    """Arquivo no PC com o conteúdo de `a`: a cópia conferida, ou uma cópia temporária feita agora."""
    pc = copia_ok(a, ler_registro())
    if pc:
        return pc
    pasta = os.path.join(ORIGINAIS, hashlib.sha1(chave(a).encode()).hexdigest()[:16])
    final = os.path.join(pasta, a["nome"])
    with _travas_arq[chave(a)]:
        if os.path.isfile(final) and os.path.getsize(final) == a["bytes"]:
            os.utime(final)
            return final
        os.makedirs(pasta, exist_ok=True)
        if os.path.exists(final):
            os.remove(final)
        iphone.copiar(a, pasta)
        if not os.path.isfile(final) or os.path.getsize(final) != a["bytes"]:
            raise RuntimeError("cópia temporária incompleta")
    threading.Thread(target=_limpar_originais, daemon=True).start()
    return final


def _arquivo(fid):
    return next((x for x in estado["arquivos"] if x["id"] == fid), None)


@app.get("/original/<fid>")
def original(fid):
    a = _arquivo(fid)
    if a is None:
        return "não encontrado", 404
    try:
        p = caminho_local(a)
    except Exception as e:
        return str(e), 500
    ext = os.path.splitext(a["nome"])[1].lower()
    if ext in (".heic", ".heif", ".dng", ".tif", ".tiff"):
        # O navegador não abre HEIC: quem converte é o leitor de imagens do próprio Windows
        # (o mesmo das miniaturas do Explorador), em JPG de até 2560 px.
        jpg = os.path.join(CACHE, "visual", hashlib.sha1(chave(a).encode()).hexdigest() + ".jpg")
        if not os.path.exists(jpg):
            img = miniatura_de_arquivo(p, 2560)
            if img is None:
                return "o Windows não abriu este formato", 415
            os.makedirs(os.path.dirname(jpg), exist_ok=True)
            img.save(jpg, quality=90)
        return send_file(jpg, mimetype="image/jpeg", max_age=86400)
    if iphone.tipo(a["nome"]) == "video":
        return send_file(p, mimetype="video/mp4", conditional=True)   # .mov do iPhone toca como mp4
    return send_file(p, conditional=True)


@app.post("/api/abrir-no-windows")
def api_abrir_windows():
    a = _arquivo(request.get_json().get("id", ""))
    if a is None:
        return jsonify(ok=False), 404
    os.startfile(caminho_local(a))
    return jsonify(ok=True)


@app.post("/api/ler")
def api_ler():
    return jsonify(ok=rodar("ler", t_ler))


@app.post("/api/copiar")
def api_copiar():
    d = request.get_json()
    destino = (d.get("destino") or "").strip().strip('"')
    if not destino or not os.path.isabs(destino):
        return jsonify(ok=False, erro="Escolha uma pasta de destino."), 400
    os.makedirs(destino, exist_ok=True)
    return jsonify(ok=rodar("copiar", t_copiar, d["ids"], destino))


@app.post("/api/apagar")
def api_apagar():
    return jsonify(ok=rodar("apagar", t_apagar, request.get_json()["ids"]))


@app.post("/api/conferir")
def api_conferir():
    pasta = (request.get_json().get("pasta") or "").strip().strip('"')
    if not os.path.isdir(pasta):
        return jsonify(ok=False, erro="Pasta não encontrada."), 400
    return jsonify(ok=rodar("conferir", t_conferir, pasta))


@app.post("/api/escolher-pasta")
def api_escolher():
    """Abre a janela padrão do Windows para escolher pasta (em processo à parte: ver escolher_pasta.py)."""
    inicial = (request.get_json() or {}).get("inicial") or os.path.join(os.path.expanduser("~"), "Pictures")
    out = subprocess.run([sys.executable, os.path.join(AQUI, "escolher_pasta.py"), inicial],
                         capture_output=True, text=True, encoding="utf-8")
    p = out.stdout.strip()
    return jsonify(pasta=os.path.normpath(p) if p else "")


@app.post("/api/abrir-pasta")
def api_abrir():
    p = request.get_json().get("pasta", "")
    if os.path.isfile(p):
        subprocess.Popen(["explorer", "/select,", p])
    elif os.path.isdir(p):
        os.startfile(p)
    return jsonify(ok=True)


def limpar_temporarios():
    """Apaga os originais trazidos do iPhone para ver e os JPG convertidos de HEIC.
    Miniaturas ficam (pouco espaço, galeria rápida). Arquivo em uso fica para a próxima."""
    import shutil
    for p in (ORIGINAIS, os.path.join(CACHE, "visual")):
        shutil.rmtree(p, ignore_errors=True)


def _ao_fechar(evento):
    # 0 Ctrl+C, 1 Ctrl+Break, 2 fechar a janela, 5 logoff, 6 desligar: o Windows dá ~5 s.
    limpar_temporarios()
    return False  # segue o encerramento normal


def main():
    import socket
    import win32api
    s = socket.socket()
    # Pergunta a este próprio computador se o app já está aberto (127.0.0.1 nunca sai da máquina).
    if s.connect_ex(("127.0.0.1", PORTA)) == 0:  # já está aberto: só mostra
        webbrowser.open(f"http://127.0.0.1:{PORTA}")
        return
    s.close()
    limpar_temporarios()  # garante, caso o fechamento anterior não tenha dado tempo
    win32api.SetConsoleCtrlHandler(_ao_fechar, True)
    iphone.com()
    rodar("ler", t_ler)
    print("Fotos do iPhone está aberto no navegador. Feche esta janela para encerrar o app.\n")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}")).start()
    app.run(host="127.0.0.1", port=PORTA, threaded=True)


if __name__ == "__main__":
    main()
