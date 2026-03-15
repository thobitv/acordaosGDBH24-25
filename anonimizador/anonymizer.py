"""
Motor de anonimização de documentos jurídicos.
Combina reconhecimento de entidades (spaCy) com padrões regex específicos
do direito brasileiro, conforme Resolução CNJ n. 615/2024.
"""
from __future__ import annotations

import re
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from . import patterns as P

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class Ocorrencia:
    """Uma ocorrência de dado sensível no texto."""
    texto_original: str
    tipo: str            # 'PESSOA', 'CPF', 'EMAIL', …
    inicio: int
    fim: int
    token: str = ''      # preenchido após geração do token


@dataclass
class ResultadoAnonimizacao:
    """Resultado completo de uma anonimização."""
    texto_anonimizado: str = ''
    mapa: dict[str, str] = field(default_factory=dict)   # token -> original
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: defaultdict(int))


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------

class Anonimizador:
    """
    Anonimiza texto de documentos jurídicos.

    Estratégia:
      1. Detectores regex (CPF, CNPJ, processo, OAB, telefone, e-mail…)
      2. Reconhecimento de entidades nomeadas via spaCy (PER, ORG, LOC)
      3. Construção de mapa token → original (determinístico: mesma string
         recebe sempre o mesmo token dentro do documento)
      4. Substituição no texto
    """

    TIPO_LABEL = {
        'PER':  'PESSOA',
        'ORG':  'ORGANIZAÇÃO',
        'LOC':  'LOCAL',
        'MISC': 'ENTIDADE',
    }

    def __init__(
        self,
        usar_spacy: bool = True,
        detectar: dict[str, bool] | None = None,
        callback_progresso: Callable[[int, str], None] | None = None,
    ):
        """
        Args:
            usar_spacy: Usar NER spaCy para detectar nomes e organizações.
            detectar: Mapa {tipo: bool} habilitando/desabilitando detectores.
            callback_progresso: função(pct_int, mensagem) para atualizar UI.
        """
        self.usar_spacy = usar_spacy
        self.detectar = detectar or {}
        self._progresso = callback_progresso or (lambda p, m: None)
        self._nlp = None  # lazy load

        # Contadores de tokens por tipo (por documento)
        self._contadores: dict[str, int] = defaultdict(int)
        # Mapa texto_original (lower) → token (dentro do documento)
        self._mapa_orig: dict[str, str] = {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def anonimizar_texto(self, texto: str) -> ResultadoAnonimizacao:
        """Anonimiza um bloco de texto e retorna o resultado."""
        self._reset()
        resultado = ResultadoAnonimizacao()

        self._progresso(10, "Detectando padrões estruturados…")
        ocorrencias = self._detectar_regex(texto)

        if self.usar_spacy and self._tipo_habilitado('PESSOA'):
            self._progresso(30, "Executando reconhecimento de entidades (NER)…")
            ocorrencias += self._detectar_ner(texto)

        self._progresso(55, "Resolvendo sobreposições…")
        ocorrencias = self._resolver_sobreposicoes(ocorrencias)

        self._progresso(70, "Gerando tokens de substituição…")
        self._atribuir_tokens(ocorrencias, resultado)

        self._progresso(85, "Substituindo texto…")
        resultado.texto_anonimizado = self._aplicar_substituicoes(texto, ocorrencias)
        resultado.ocorrencias = ocorrencias

        for oc in ocorrencias:
            resultado.stats[oc.tipo] += 1

        self._progresso(100, "Concluído.")
        return resultado

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _reset(self):
        self._contadores = defaultdict(int)
        self._mapa_orig = {}

    def _tipo_habilitado(self, tipo: str) -> bool:
        return self.detectar.get(tipo, True)

    def _detectar_regex(self, texto: str) -> list[Ocorrencia]:
        ocorrencias: list[Ocorrencia] = []
        for nome, regex in P.DETECTORES:
            if not self._tipo_habilitado(nome):
                continue
            for m in regex.finditer(texto):
                ocorrencias.append(Ocorrencia(
                    texto_original=m.group(),
                    tipo=nome,
                    inicio=m.start(),
                    fim=m.end(),
                ))
        return ocorrencias

    def _detectar_ner(self, texto: str) -> list[Ocorrencia]:
        """Detecta entidades nomeadas com spaCy."""
        nlp = self._obter_nlp()
        if nlp is None:
            return []

        ocorrencias: list[Ocorrencia] = []
        # spaCy tem limite de tamanho; processar em blocos se necessário
        max_len = nlp.max_length - 1
        blocos = [texto[i:i+max_len] for i in range(0, len(texto), max_len)]
        offset = 0
        for bloco in blocos:
            doc = nlp(bloco)
            for ent in doc.ents:
                label = ent.label_
                tipo = self.TIPO_LABEL.get(label)
                if tipo is None:
                    offset += len(bloco)
                    continue
                if not self._tipo_habilitado(tipo):
                    continue
                texto_ent = ent.text.strip()
                # Filtrar stopwords e entidades muito curtas
                if (len(texto_ent) < 3
                        or texto_ent.lower() in P.STOPWORDS_JURIDICAS):
                    continue
                ocorrencias.append(Ocorrencia(
                    texto_original=texto_ent,
                    tipo=tipo,
                    inicio=offset + ent.start_char,
                    fim=offset + ent.end_char,
                ))
            offset += len(bloco)
        return ocorrencias

    def _obter_nlp(self):
        """Carrega o modelo spaCy (lazy) – retorna None se não disponível."""
        if self._nlp is not None:
            return self._nlp
        try:
            import spacy  # noqa: PLC0415
            try:
                self._nlp = spacy.load('pt_core_news_lg')
            except OSError:
                try:
                    self._nlp = spacy.load('pt_core_news_sm')
                except OSError:
                    logger.warning(
                        "Modelo spaCy pt_core_news não encontrado. "
                        "Execute: python -m spacy download pt_core_news_lg"
                    )
                    self._nlp = None
        except ImportError:
            logger.warning("spaCy não instalado. NER desabilitado.")
            self._nlp = None
        return self._nlp

    @staticmethod
    def _resolver_sobreposicoes(ocorrencias: list[Ocorrencia]) -> list[Ocorrencia]:
        """Remove ocorrências sobrepostas, priorizando as de maior comprimento."""
        ocorrencias.sort(key=lambda o: (o.inicio, -(o.fim - o.inicio)))
        resultado: list[Ocorrencia] = []
        ultimo_fim = -1
        for oc in ocorrencias:
            if oc.inicio >= ultimo_fim:
                resultado.append(oc)
                ultimo_fim = oc.fim
        return resultado

    def _atribuir_tokens(
        self,
        ocorrencias: list[Ocorrencia],
        resultado: ResultadoAnonimizacao,
    ):
        """Gera tokens determinísticos e preenche o mapa inverso."""
        for oc in ocorrencias:
            chave = (oc.tipo, oc.texto_original.strip().lower())
            if chave in self._mapa_orig:
                oc.token = self._mapa_orig[chave]
            else:
                self._contadores[oc.tipo] += 1
                n = self._contadores[oc.tipo]
                token = f'[{oc.tipo}_{n}]'
                self._mapa_orig[chave] = token
                oc.token = token
            # mapa inverso: token → texto original
            resultado.mapa[oc.token] = oc.texto_original.strip()

    @staticmethod
    def _aplicar_substituicoes(texto: str, ocorrencias: list[Ocorrencia]) -> str:
        """Substitui as ocorrências de trás para frente para preservar índices."""
        partes: list[str] = []
        ultimo = len(texto)
        for oc in reversed(ocorrencias):
            partes.append(texto[oc.fim:ultimo])
            partes.append(oc.token)
            ultimo = oc.inicio
        partes.append(texto[:ultimo])
        return ''.join(reversed(partes))


# ---------------------------------------------------------------------------
# Geração do índice de substituições
# ---------------------------------------------------------------------------

def gerar_indice_json(
    resultado: ResultadoAnonimizacao,
    arquivo_original: str,
) -> str:
    """Serializa o índice de substituições em JSON."""
    dados = {
        'metadata': {
            'arquivo_original': arquivo_original,
            'anonimizado_em': datetime.now().isoformat(timespec='seconds'),
            'total_substituicoes': len(resultado.mapa),
            'por_tipo': dict(resultado.stats),
            'resolucao_cnj': '615/2024',
        },
        'substituicoes': resultado.mapa,
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def gerar_indice_txt(resultado: ResultadoAnonimizacao, arquivo_original: str) -> str:
    """Gera índice em texto plano (útil para localizar-e-substituir)."""
    linhas = [
        '=' * 70,
        'ÍNDICE DE ANONIMIZAÇÃO',
        f'Arquivo original : {arquivo_original}',
        f'Data/hora        : {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}',
        f'Total de itens   : {len(resultado.mapa)}',
        f'Resolução CNJ    : n. 615/2024',
        '=' * 70,
        '',
        'COMO USAR:',
        '  Em um editor de texto, use "Localizar e Substituir":',
        '    • Localizar:   o TOKEN entre colchetes (ex.: [PESSOA_1])',
        '    • Substituir:  o ORIGINAL correspondente abaixo',
        '',
        '-' * 70,
        f'{"TOKEN":<25} {"ORIGINAL"}',
        '-' * 70,
    ]
    for token, original in sorted(resultado.mapa.items()):
        linhas.append(f'{token:<25} {original}')
    linhas += ['', '=' * 70]
    return '\n'.join(linhas)
