"""
Processamento de PDFs: extração de texto e geração do PDF anonimizado.

Usa PyMuPDF (fitz) para:
  - Extrair texto com posicionamento por página
  - Aplicar redações (substituição textual) no PDF original
  - Salvar o PDF anonimizado mantendo layout/imagens

Para PDFs digitalizados (somente imagem), o módulo avisa o usuário e
pode acionar OCR via pytesseract se disponível.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------

def extrair_texto(caminho_pdf: str) -> tuple[str, bool]:
    """
    Extrai o texto completo do PDF.

    Returns:
        (texto, tem_texto_nativo)
        tem_texto_nativo=False indica PDF escaneado que precisaria de OCR.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF não instalado. Execute: pip install pymupdf"
        ) from exc

    doc = fitz.open(caminho_pdf)
    partes: list[str] = []
    tem_texto = False

    for pag in doc:
        texto_pag = pag.get_text('text')
        if texto_pag.strip():
            tem_texto = True
        partes.append(texto_pag)

    doc.close()
    return '\n'.join(partes), tem_texto


def extrair_texto_com_ocr(caminho_pdf: str) -> str:
    """Extrai texto de PDF escaneado usando pytesseract + pdf2image."""
    try:
        from pdf2image import convert_from_path  # noqa: PLC0415
        import pytesseract  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Para PDFs escaneados instale: pip install pdf2image pytesseract\n"
            "E o Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
        ) from exc

    imagens = convert_from_path(caminho_pdf, dpi=300)
    partes: list[str] = []
    for img in imagens:
        texto = pytesseract.image_to_string(img, lang='por')
        partes.append(texto)
    return '\n'.join(partes)


# ---------------------------------------------------------------------------
# Geração do PDF anonimizado
# ---------------------------------------------------------------------------

def gerar_pdf_anonimizado(
    caminho_entrada: str,
    caminho_saida: str,
    mapa_substituicoes: dict[str, str],
    callback_progresso: Callable[[int, str], None] | None = None,
) -> int:
    """
    Gera PDF anonimizado substituindo cada texto original pelo respectivo token.

    Estratégia:
      Para cada página, busca cada texto original com fitz.Page.search_for()
      e aplica uma redação (retângulo branco + texto do token) sobre ele.

    Returns:
        Número total de redações aplicadas.
    """
    progresso = callback_progresso or (lambda p, m: None)

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF não instalado.") from exc

    doc = fitz.open(caminho_entrada)
    total_redacoes = 0
    n_pags = len(doc)

    # Invertemos o mapa: original -> token
    # (o resultado da anonimização já tem token->original; aqui queremos original->token)
    mapa_inv = {v: k for k, v in mapa_substituicoes.items()}

    for i, pag in enumerate(doc):
        progresso(
            int(10 + 80 * i / max(n_pags, 1)),
            f"Processando página {i+1}/{n_pags}…"
        )

        # Fase 1: coletar todas as redações da página
        redacoes: list[tuple] = []  # (rect, token)
        for texto_orig, token in mapa_inv.items():
            areas = pag.search_for(texto_orig, quads=False)
            for rect in areas:
                redacoes.append((rect, token))
                total_redacoes += 1

        if not redacoes:
            continue

        # Fase 2: adicionar anotações de redação
        for rect, token in redacoes:
            ann = pag.add_redact_annot(
                quad=rect,
                text=token,
                fontname='helv',
                fontsize=_estimar_fontsize(rect, token),
                align=fitz.TEXT_ALIGN_LEFT,
                fill=(1, 1, 1),   # fundo branco
                text_color=(0, 0, 0),
            )
            ann.set_border(width=0)

        # Fase 3: aplicar as redações
        pag.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,   # preservar imagens
        )

    progresso(95, "Salvando PDF anonimizado…")
    doc.save(caminho_saida, garbage=4, deflate=True)
    doc.close()
    progresso(100, "PDF salvo.")
    return total_redacoes


def _estimar_fontsize(rect, token: str) -> float:
    """Estima tamanho de fonte para caber o token no retângulo."""
    largura = rect.width
    altura = rect.height
    # Aproximação: cada char tem ~0.5 * fontsize de largura
    tamanho_por_largura = (largura / max(len(token), 1)) / 0.55
    tamanho_por_altura = altura * 0.85
    return max(4.0, min(tamanho_por_largura, tamanho_por_altura, 11.0))


# ---------------------------------------------------------------------------
# Geração de PDF alternativo baseado em texto puro
# (fallback quando o original tem layout complexo ou é escaneado)
# ---------------------------------------------------------------------------

def gerar_pdf_texto_anonimizado(
    texto_anonimizado: str,
    caminho_saida: str,
    titulo: str = 'Documento Anonimizado',
) -> None:
    """Cria um PDF simples com o texto anonimizado (fallback)."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF não instalado.") from exc

    doc = fitz.open()
    margem = 50
    largura_pag, altura_pag = fitz.paper_size('a4')
    rect_texto = fitz.Rect(margem, margem, largura_pag - margem, altura_pag - margem)

    # Quebrar em blocos de ~3000 chars para paginação simples
    blocos = _paginar_texto(texto_anonimizado, max_chars=3000)

    for bloco in blocos:
        pag = doc.new_page(width=largura_pag, height=altura_pag)
        pag.insert_textbox(
            rect_texto,
            bloco,
            fontname='helv',
            fontsize=10,
            color=(0, 0, 0),
        )

    doc.save(caminho_saida, garbage=4, deflate=True)
    doc.close()


def _paginar_texto(texto: str, max_chars: int) -> list[str]:
    """Divide texto em blocos respeitando quebras de parágrafo."""
    paragrafos = texto.split('\n')
    blocos: list[str] = []
    atual: list[str] = []
    chars = 0
    for p in paragrafos:
        if chars + len(p) > max_chars and atual:
            blocos.append('\n'.join(atual))
            atual = []
            chars = 0
        atual.append(p)
        chars += len(p) + 1
    if atual:
        blocos.append('\n'.join(atual))
    return blocos or ['']


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def validar_pdf(caminho: str) -> tuple[bool, str]:
    """Verifica se o arquivo é um PDF válido e legível."""
    try:
        import fitz
        doc = fitz.open(caminho)
        n = len(doc)
        doc.close()
        if n == 0:
            return False, "PDF sem páginas."
        return True, f"PDF válido ({n} página{'s' if n > 1 else ''})."
    except Exception as exc:
        return False, f"Erro ao abrir PDF: {exc}"


def sugerir_nome_saida(caminho_entrada: str) -> str:
    """Sugere nome do arquivo de saída com sufixo '_anonimizado'."""
    p = Path(caminho_entrada)
    return str(p.parent / f"{p.stem}_anonimizado{p.suffix}")


def sugerir_nome_indice(caminho_entrada: str, extensao: str = '.json') -> str:
    """Sugere nome do arquivo de índice."""
    p = Path(caminho_entrada)
    return str(p.parent / f"{p.stem}_indice{extensao}")
