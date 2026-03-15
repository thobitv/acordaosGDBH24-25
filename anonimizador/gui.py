"""
Interface gráfica (tkinter/ttk) para o Anonimizador de Documentos Jurídicos.
Resolução CNJ n. 615/2024.
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .anonymizer import Anonimizador, gerar_indice_json, gerar_indice_txt
from .pdf_processor import (
    extrair_texto,
    gerar_pdf_anonimizado,
    gerar_pdf_texto_anonimizado,
    sugerir_nome_indice,
    sugerir_nome_saida,
    validar_pdf,
)

# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------
AZUL_CNJ   = '#003580'
AZUL_CLARO = '#e8eff8'
VERDE_OK   = '#1a7a4a'
VERMELHO   = '#b91c1c'
CINZA_FG   = '#374151'
BRANCO     = '#ffffff'
FUNDO      = '#f4f6fa'


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Anonimizador Jurídico – Res. CNJ n. 615/2024')
        self.geometry('900x720')
        self.minsize(780, 600)
        self.configure(bg=FUNDO)
        self.resizable(True, True)

        # Estado
        self._arquivo_pdf: str = ''
        self._fila: queue.Queue = queue.Queue()
        self._processando = False

        self._configurar_estilos()
        self._construir_layout()
        self._checar_fila()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _configurar_estilos(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TFrame',      background=FUNDO)
        s.configure('Card.TFrame', background=BRANCO, relief='flat')
        s.configure('TLabel',      background=FUNDO,  foreground=CINZA_FG,
                    font=('Segoe UI', 10))
        s.configure('Header.TLabel', background=AZUL_CNJ, foreground=BRANCO,
                    font=('Segoe UI', 13, 'bold'))
        s.configure('Sub.TLabel',  background=BRANCO, foreground=CINZA_FG,
                    font=('Segoe UI', 9))
        s.configure('Card.TLabel', background=BRANCO, foreground=CINZA_FG,
                    font=('Segoe UI', 10))
        s.configure('OK.TLabel',   background=BRANCO, foreground=VERDE_OK,
                    font=('Segoe UI', 9, 'bold'))
        s.configure('Erro.TLabel', background=BRANCO, foreground=VERMELHO,
                    font=('Segoe UI', 9, 'bold'))
        s.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'),
                    background=AZUL_CNJ, foreground=BRANCO)
        s.map('Accent.TButton',
              background=[('active', '#00469e'), ('disabled', '#94a3b8')],
              foreground=[('disabled', '#cbd5e1')])
        s.configure('TButton', font=('Segoe UI', 9))
        s.configure('TCheckbutton', background=BRANCO, foreground=CINZA_FG,
                    font=('Segoe UI', 9))
        s.configure('TLabelframe',       background=BRANCO)
        s.configure('TLabelframe.Label', background=BRANCO, foreground=AZUL_CNJ,
                    font=('Segoe UI', 9, 'bold'))
        s.configure('TProgressbar', troughcolor='#e2e8f0',
                    background=AZUL_CNJ, thickness=10)

    def _construir_layout(self):
        # Cabeçalho
        header = tk.Frame(self, bg=AZUL_CNJ, height=56)
        header.pack(fill='x')
        tk.Label(
            header,
            text='  Anonimizador de Documentos Jurídicos',
            bg=AZUL_CNJ, fg=BRANCO,
            font=('Segoe UI', 14, 'bold'),
            anchor='w',
        ).pack(side='left', pady=12, padx=10)
        tk.Label(
            header,
            text='Res. CNJ n. 615/2024  ',
            bg=AZUL_CNJ, fg='#93c5fd',
            font=('Segoe UI', 9),
            anchor='e',
        ).pack(side='right', pady=12)

        # Corpo
        corpo = ttk.Frame(self)
        corpo.pack(fill='both', expand=True, padx=18, pady=14)

        esq = ttk.Frame(corpo)
        esq.pack(side='left', fill='both', expand=True, padx=(0, 8))
        dir_ = ttk.Frame(corpo)
        dir_.pack(side='right', fill='y', padx=(8, 0))

        self._construir_painel_arquivo(esq)
        self._construir_painel_opcoes(dir_)
        self._construir_painel_saida(esq)
        self._construir_painel_log(esq)
        self._construir_barra_botoes(esq)

    # -- Arquivo de entrada -----------------------------------------------
    def _construir_painel_arquivo(self, pai):
        card = ttk.LabelFrame(pai, text=' 1. Arquivo PDF ', padding=10)
        card.pack(fill='x', pady=(0, 10))

        linha = ttk.Frame(card)
        linha.pack(fill='x')
        self._var_arquivo = tk.StringVar(value='Nenhum arquivo selecionado')
        ttk.Entry(
            linha, textvariable=self._var_arquivo, state='readonly', width=55
        ).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ttk.Button(
            linha, text='Selecionar PDF…', command=self._selecionar_pdf
        ).pack(side='right')

        self._lbl_status_pdf = ttk.Label(card, text='', style='Sub.TLabel')
        self._lbl_status_pdf.pack(anchor='w', pady=(4, 0))

    # -- Opções de anonimização -------------------------------------------
    def _construir_painel_opcoes(self, pai):
        card = ttk.LabelFrame(pai, text=' Opções ', padding=10)
        card.pack(fill='x', pady=(0, 10))

        self._vars_detector: dict[str, tk.BooleanVar] = {}
        detectores = [
            ('PESSOA',       'Nomes de pessoas (NER)'),
            ('ORGANIZAÇÃO',  'Organizações (NER)'),
            ('LOCAL',        'Locais (NER)'),
            ('CPF',          'CPF'),
            ('CNPJ',         'CNPJ'),
            ('PROCESSO',     'Número do processo'),
            ('OAB',          'OAB'),
            ('EMAIL',        'E-mail'),
            ('TELEFONE',     'Telefone'),
            ('CEP',          'CEP'),
            ('RG',           'RG'),
            ('PLACA',        'Placa de veículo'),
            ('MATRICULA',    'Matrícula'),
        ]
        for chave, rotulo in detectores:
            v = tk.BooleanVar(value=True)
            self._vars_detector[chave] = v
            ttk.Checkbutton(card, text=rotulo, variable=v).pack(anchor='w')

        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=8)

        self._var_spacy = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            card, text='Usar NER (spaCy)', variable=self._var_spacy
        ).pack(anchor='w')

        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=8)

        tk.Label(card, text='Formato do índice:', bg=BRANCO,
                 font=('Segoe UI', 9)).pack(anchor='w')
        self._var_formato_indice = tk.StringVar(value='ambos')
        for val, txt in [('json', 'JSON'), ('txt', 'TXT'), ('ambos', 'Ambos')]:
            ttk.Radiobutton(
                card, text=txt, variable=self._var_formato_indice, value=val
            ).pack(anchor='w')

        ttk.Separator(card, orient='horizontal').pack(fill='x', pady=8)

        self._var_pdf_texto = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            card,
            text='PDF alternativo\n(texto puro)',
            variable=self._var_pdf_texto,
        ).pack(anchor='w')

    # -- Destino da saída -------------------------------------------------
    def _construir_painel_saida(self, pai):
        card = ttk.LabelFrame(pai, text=' 2. Destino dos arquivos ', padding=10)
        card.pack(fill='x', pady=(0, 10))

        linha = ttk.Frame(card)
        linha.pack(fill='x')
        self._var_saida = tk.StringVar(value='')
        ttk.Entry(
            linha, textvariable=self._var_saida, width=55
        ).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ttk.Button(
            linha, text='Escolher pasta…', command=self._selecionar_saida
        ).pack(side='right')

        ttk.Label(
            card,
            text='Se vazio, os arquivos serão salvos na mesma pasta do PDF.',
            style='Sub.TLabel',
        ).pack(anchor='w', pady=(4, 0))

    # -- Log de execução --------------------------------------------------
    def _construir_painel_log(self, pai):
        card = ttk.LabelFrame(pai, text=' Log ', padding=6)
        card.pack(fill='both', expand=True, pady=(0, 8))

        self._txt_log = scrolledtext.ScrolledText(
            card, height=10, state='disabled',
            font=('Consolas', 9), wrap='word',
            bg='#1e293b', fg='#e2e8f0',
            insertbackground='white',
        )
        self._txt_log.pack(fill='both', expand=True)
        self._txt_log.tag_config('ok',   foreground='#4ade80')
        self._txt_log.tag_config('erro', foreground='#f87171')
        self._txt_log.tag_config('info', foreground='#93c5fd')

        self._barra = ttk.Progressbar(
            card, mode='determinate', maximum=100, style='TProgressbar'
        )
        self._barra.pack(fill='x', pady=(4, 0))
        self._lbl_pct = ttk.Label(card, text='', style='Sub.TLabel')
        self._lbl_pct.pack(anchor='e')

    # -- Botões -----------------------------------------------------------
    def _construir_barra_botoes(self, pai):
        barra = ttk.Frame(pai)
        barra.pack(fill='x')

        self._btn_processar = ttk.Button(
            barra,
            text='Anonimizar Documento',
            style='Accent.TButton',
            command=self._iniciar_processamento,
        )
        self._btn_processar.pack(side='left', ipadx=16, ipady=4)

        ttk.Button(
            barra, text='Limpar log', command=self._limpar_log
        ).pack(side='left', padx=8)

        ttk.Button(
            barra, text='Sobre / CNJ', command=self._mostrar_sobre
        ).pack(side='right')

    # ------------------------------------------------------------------
    # Ações da interface
    # ------------------------------------------------------------------

    def _selecionar_pdf(self):
        caminho = filedialog.askopenfilename(
            title='Selecionar arquivo PDF',
            filetypes=[('Arquivos PDF', '*.pdf'), ('Todos', '*.*')],
        )
        if not caminho:
            return
        self._arquivo_pdf = caminho
        self._var_arquivo.set(Path(caminho).name)

        ok, msg = validar_pdf(caminho)
        if ok:
            self._lbl_status_pdf.configure(text=f'✓ {msg}', style='OK.TLabel')
            pasta = str(Path(caminho).parent)
            if not self._var_saida.get():
                self._var_saida.set(pasta)
        else:
            self._lbl_status_pdf.configure(text=f'✗ {msg}', style='Erro.TLabel')
            self._arquivo_pdf = ''

    def _selecionar_saida(self):
        pasta = filedialog.askdirectory(title='Selecionar pasta de destino')
        if pasta:
            self._var_saida.set(pasta)

    def _iniciar_processamento(self):
        if self._processando:
            return
        if not self._arquivo_pdf:
            messagebox.showwarning('Atenção', 'Selecione um arquivo PDF primeiro.')
            return

        self._processando = True
        self._btn_processar.configure(state='disabled')
        self._barra['value'] = 0
        self._lbl_pct.configure(text='')
        self._log('Iniciando anonimização…', 'info')

        thread = threading.Thread(target=self._processar, daemon=True)
        thread.start()

    def _processar(self):
        """Executado em thread separada."""
        try:
            arquivo   = self._arquivo_pdf
            pasta     = self._var_saida.get() or str(Path(arquivo).parent)
            stem      = Path(arquivo).stem
            detectar  = {k: v.get() for k, v in self._vars_detector.items()}
            usar_spacy = self._var_spacy.get()
            fmt_indice = self._var_formato_indice.get()
            pdf_texto  = self._var_pdf_texto.get()

            # Caminhos de saída
            saida_pdf  = os.path.join(pasta, f'{stem}_anonimizado.pdf')
            saida_json = os.path.join(pasta, f'{stem}_indice.json')
            saida_txt  = os.path.join(pasta, f'{stem}_indice.txt')

            # 1. Extrair texto
            self._enfileirar_progresso(5, 'Extraindo texto do PDF…')
            texto, tem_texto = extrair_texto(arquivo)
            if not tem_texto:
                self._enfileirar_log(
                    'AVISO: PDF pode ser digitalizado (imagem). '
                    'A extração de texto pode estar incompleta. '
                    'Considere ativar OCR.', 'erro'
                )

            # 2. Anonimizar
            self._enfileirar_progresso(10, 'Anonimizando texto…')
            anonimizador = Anonimizador(
                usar_spacy=usar_spacy,
                detectar=detectar,
                callback_progresso=self._enfileirar_progresso,
            )
            resultado = anonimizador.anonimizar_texto(texto)

            if not resultado.mapa:
                self._enfileirar_log(
                    'Nenhum dado sensível identificado. '
                    'Verifique se o PDF contém texto e se os detectores estão habilitados.',
                    'erro'
                )
                self._enfileirar_fim(False)
                return

            n_subst = len(resultado.mapa)
            self._enfileirar_log(
                f'{n_subst} item(ns) identificado(s): '
                + ', '.join(f'{t}={v}' for t, v in resultado.stats.items()),
                'ok'
            )

            # 3. Gerar PDF anonimizado
            self._enfileirar_progresso(55, 'Gerando PDF anonimizado…')
            n_redacoes = gerar_pdf_anonimizado(
                caminho_entrada=arquivo,
                caminho_saida=saida_pdf,
                mapa_substituicoes=resultado.mapa,
                callback_progresso=self._enfileirar_progresso,
            )
            self._enfileirar_log(
                f'PDF salvo: {Path(saida_pdf).name}  ({n_redacoes} redação(ões))', 'ok'
            )

            # 3b. PDF texto puro (opcional)
            if pdf_texto:
                saida_pdf_txt = os.path.join(pasta, f'{stem}_anonimizado_texto.pdf')
                gerar_pdf_texto_anonimizado(resultado.texto_anonimizado, saida_pdf_txt)
                self._enfileirar_log(f'PDF texto: {Path(saida_pdf_txt).name}', 'ok')

            # 4. Salvar índices
            self._enfileirar_progresso(95, 'Salvando índice de substituições…')
            nome_orig = Path(arquivo).name

            if fmt_indice in ('json', 'ambos'):
                conteudo_json = gerar_indice_json(resultado, nome_orig)
                Path(saida_json).write_text(conteudo_json, encoding='utf-8')
                self._enfileirar_log(f'Índice JSON: {Path(saida_json).name}', 'ok')

            if fmt_indice in ('txt', 'ambos'):
                conteudo_txt = gerar_indice_txt(resultado, nome_orig)
                Path(saida_txt).write_text(conteudo_txt, encoding='utf-8')
                self._enfileirar_log(f'Índice TXT: {Path(saida_txt).name}', 'ok')

            self._enfileirar_progresso(100, 'Concluído!')
            self._enfileirar_log(
                f'Arquivos salvos em: {pasta}', 'ok'
            )
            self._enfileirar_fim(True, pasta)

        except Exception as exc:
            import traceback
            self._enfileirar_log(f'ERRO: {exc}', 'erro')
            self._enfileirar_log(traceback.format_exc(), 'erro')
            self._enfileirar_fim(False)

    # ------------------------------------------------------------------
    # Comunicação thread → GUI via fila
    # ------------------------------------------------------------------

    def _enfileirar_progresso(self, pct: int, msg: str):
        self._fila.put(('progresso', pct, msg))

    def _enfileirar_log(self, msg: str, tag: str = ''):
        self._fila.put(('log', msg, tag))

    def _enfileirar_fim(self, sucesso: bool, pasta: str = ''):
        self._fila.put(('fim', sucesso, pasta))

    def _checar_fila(self):
        """Polling da fila a cada 100 ms para atualizar a GUI na thread principal."""
        try:
            while True:
                item = self._fila.get_nowait()
                tipo = item[0]
                if tipo == 'progresso':
                    _, pct, msg = item
                    self._barra['value'] = pct
                    self._lbl_pct.configure(text=f'{pct}%  {msg}')
                elif tipo == 'log':
                    _, msg, tag = item
                    self._log(msg, tag)
                elif tipo == 'fim':
                    _, sucesso, pasta = item
                    self._processando = False
                    self._btn_processar.configure(state='normal')
                    if sucesso:
                        resp = messagebox.askyesno(
                            'Concluído',
                            f'Anonimização concluída com sucesso!\n\n'
                            f'Arquivos salvos em:\n{pasta}\n\n'
                            f'Deseja abrir a pasta?',
                        )
                        if resp:
                            self._abrir_pasta(pasta)
                    else:
                        messagebox.showerror(
                            'Erro',
                            'Ocorreu um erro durante o processamento.\n'
                            'Verifique o log para detalhes.',
                        )
        except queue.Empty:
            pass
        finally:
            self.after(100, self._checar_fila)

    # ------------------------------------------------------------------
    # Auxiliares da GUI
    # ------------------------------------------------------------------

    def _log(self, msg: str, tag: str = ''):
        self._txt_log.configure(state='normal')
        self._txt_log.insert('end', msg + '\n', tag or None)
        self._txt_log.see('end')
        self._txt_log.configure(state='disabled')

    def _limpar_log(self):
        self._txt_log.configure(state='normal')
        self._txt_log.delete('1.0', 'end')
        self._txt_log.configure(state='disabled')
        self._barra['value'] = 0
        self._lbl_pct.configure(text='')

    @staticmethod
    def _abrir_pasta(pasta: str):
        import subprocess, sys
        if sys.platform.startswith('win'):
            os.startfile(pasta)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', pasta])
        else:
            subprocess.Popen(['xdg-open', pasta])

    def _mostrar_sobre(self):
        sobre = tk.Toplevel(self)
        sobre.title('Sobre')
        sobre.geometry('480x340')
        sobre.configure(bg=BRANCO)
        sobre.resizable(False, False)

        tk.Frame(sobre, bg=AZUL_CNJ, height=6).pack(fill='x')

        tk.Label(
            sobre,
            text='Anonimizador de Documentos Jurídicos',
            bg=BRANCO, fg=AZUL_CNJ,
            font=('Segoe UI', 13, 'bold'),
        ).pack(pady=(20, 4))

        corpo_txt = (
            'Esta ferramenta anonimiza processos judiciais e documentos PDF\n'
            'para uso seguro em modelos de Inteligência Artificial, conforme\n'
            'a Resolução CNJ n. 615/2024.\n\n'
            'Dados substituídos: nomes, CPF, CNPJ, OAB, RG, e-mail,\n'
            'telefone, endereço, número do processo e outros.\n\n'
            'O índice de substituições permite reverter os tokens gerados\n'
            'nos textos criados pela IA (minuta de voto/decisão), mantendo\n'
            'os dados pessoais exclusivamente na máquina local do usuário.\n\n'
            'Tecnologias: Python · PyMuPDF · spaCy (pt_core_news_lg)\n'
        )
        tk.Label(
            sobre, text=corpo_txt,
            bg=BRANCO, fg=CINZA_FG,
            font=('Segoe UI', 10),
            justify='center',
        ).pack(padx=20)

        def abrir_cnj():
            webbrowser.open('https://atos.cnj.jus.br/atos/detalhar/5815')

        ttk.Button(sobre, text='Resolução CNJ n. 615/2024 →', command=abrir_cnj
                   ).pack(pady=8)
        ttk.Button(sobre, text='Fechar', command=sobre.destroy).pack()


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def iniciar():
    app = App()
    app.mainloop()
