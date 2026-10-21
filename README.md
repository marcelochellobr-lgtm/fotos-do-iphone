# Fotos do iPhone

Veja as fotos e vídeos do seu iPhone no computador, copie para o PC e apague do aparelho só o que
já tem cópia conferida. Para liberar espaço sem pagar iCloud.

Gratuito, código aberto, **funciona sem internet**. Windows 10 ou 11.

## Baixar e usar

1. Em [**Releases**](https://github.com/marcelochellobr-lgtm/fotos-do-iphone/releases/latest), baixe
   o arquivo `Fotos-do-iPhone-v1.0.zip`.
2. Clique com o botão direito no arquivo → **Extrair tudo** → escolha uma pasta (ex.: Documentos).
3. Conecte o iPhone no cabo, desbloqueie e toque em **Confiar**.
4. Dê dois cliques em **`Abrir Fotos do iPhone.bat`**. A tela abre no navegador.
5. Para desligar, feche a janela preta.

Na primeira vez o Windows pode mostrar **"O Windows protegeu o computador"**: aparece para arquivo
baixado da internet sem assinatura de empresa. **Mais informações → Executar assim mesmo.**

## O que ele faz

- Galeria por mês, com miniatura, data e tamanho; vídeo toca na tela.
- Uma foto do iPhone (HEIC + vídeo da Live + versão editada + .AAE) aparece como um item só.
- Barra do armazenamento do iPhone: quanto já está no PC, quanto só no iPhone, quanto está livre.
- **Copiar para o PC:** você escolhe a pasta; cada arquivo é conferido pelo tamanho depois de copiado.
- **Apagar do iPhone:** só o que tem cópia no PC com mesmo nome e tamanho exato, conferida de novo na
  hora de apagar. **É definitivo** — não vai para "Apagados recentemente". Teste com uma foto primeiro.

## Segurança, sem letra miúda

| Pergunta | Resposta |
|---|---|
| Precisa de internet? | **Não.** Só para baixar o .zip. Pode usar com o Wi-Fi desligado. |
| Fala com algum site, servidor ou API? | **Não.** O app só escuta em `127.0.0.1`, o endereço que existe apenas dentro do seu computador — nem outro aparelho da sua casa acessa. |
| Instala alguma coisa? | **Não.** Sem instalador, sem senha de administrador, sem mexer no registro do Windows, sem nada rodando escondido. |
| Como desinstalar? | Apague a pasta. |
| Onde ficam os meus dados? | Na pasta `dados`, ao lado do app. Nada sai do computador. |
| Qual o risco real? | Apagar foto. É para isso que existe a trava de conferência. |

Não confie: confira. Todo o app está na pasta [`app/`](app/) — quatro arquivos de Python e uma
página HTML, em texto. Dá para pedir a qualquer IA que leia e explique.

## O que vem no pacote

```
Fotos do iPhone/
├── Abrir Fotos do iPhone.bat          o botão de ligar (texto: abra no Bloco de Notas)
├── Criar atalho na Area de Trabalho.bat   opcional
├── LEIA-ME.txt
├── app/                               o app, em texto
│   ├── app.py                         lê, copia, confere e apaga
│   ├── iphone.py                      conversa com o iPhone pelo próprio Windows
│   ├── miniatura.py                   pede ao Windows as miniaturas
│   ├── escolher_pasta.py              janela do Windows para escolher pasta
│   └── index.html                     a tela no navegador
└── python/                            Python oficial (python.org), versão portátil,
                                       assinado pela Python Software Foundation, com:
                                       Flask (tela local), pywin32 e comtypes (conversa
                                       com o Windows), Pillow (miniaturas)
```

O pacote é montado por [`montar_pacote.py`](montar_pacote.py): baixa o Python portátil do
python.org, confere a assinatura digital, põe as bibliotecas em versões fixas e compacta.

## Se o iPhone não aparecer

- Desbloqueie e confira se ele pediu "Confiar neste computador".
- Se o "Apple iPhone" não aparece no Explorador de Arquivos, falta o driver da Apple: instale o app
  gratuito **Apple Devices** da Microsoft Store.
- No iPhone: Ajustes → Apps → Fotos → Transferir para Mac ou PC → **Manter originais**.

## Limitações

Windows só (sem Mac). Um iPhone por vez. O espaço livre que o iPhone informa ao PC só atualiza ao
reconectar o cabo; até lá o app soma o que apagou.

---

Feito por [Marcelo Chello](https://www.youtube.com/@marcelochello) com Claude Code, sem saber
programar. Licença [MIT](LICENSE).
