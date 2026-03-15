"""
Padrões regex para identificação de dados sensíveis em documentos jurídicos brasileiros.
Conforme Resolução CNJ n. 615/2024.
"""
import re

# ---------------------------------------------------------------------------
# Padrões estruturados (alta precisão)
# ---------------------------------------------------------------------------

# CPF: 000.000.000-00 ou 00000000000
CPF = re.compile(
    r'\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?\d{2}\b'
)

# CNPJ: 00.000.000/0000-00 ou 00000000000000
CNPJ = re.compile(
    r'\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}\b'
)

# Número de processo CNJ: 0000000-00.0000.0.00.0000
PROCESSO = re.compile(
    r'\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b'
)

# Número de processo formato antigo
PROCESSO_ANTIGO = re.compile(
    r'\b\d{4,6}[\.\-/]\d{2,4}[\.\-/]\d{2,4}(?:[\.\-/]\d{1,4})?\b'
)

# OAB: OAB/SP 123.456 ou OAB nº 123456/SP
OAB = re.compile(
    r'\bOAB[/\s]?(?:n[º°\.]?\s*)?[A-Z]{2}[/\s]?\d[\d\.]+\b'
    r'|\bOAB[/\s]?\d[\d\.]+[/\s]?[A-Z]{2}\b',
    re.IGNORECASE
)

# CEP: 00000-000 ou 00000000
CEP = re.compile(
    r'\bCEP[:\s]?\d{5}-?\d{3}\b'
    r'|\b\d{5}-\d{3}\b',
    re.IGNORECASE
)

# E-mail
EMAIL = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

# Telefone: (00) 00000-0000, (00) 0000-0000, 0800-000-0000
TELEFONE = re.compile(
    r'\b(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4}[-\s]?\d{4}\b'
    r'|\b0800[-\s]?\d{3}[-\s]?\d{4}\b'
)

# RG: formatos variados por estado
RG = re.compile(
    r'\bRG[:\s]?\d[\d\.\-/X]+\b'
    r'|\b\d{1,2}[\.\-]?\d{3}[\.\-]?\d{3}[-]?[0-9X]\b',
    re.IGNORECASE
)

# Número de matrícula / registro (magistrado, servidor)
MATRICULA = re.compile(
    r'\bmatr[íi]cula[:\s]?\d[\d\.\-]+\b',
    re.IGNORECASE
)

# Conta bancária / agência
CONTA_BANCARIA = re.compile(
    r'\bagência[:\s]?\d{4}[-\s]?\d?\s+conta[:\s]?\d[\d\.\-]+[-\s]?\d\b'
    r'|\bconta[:\s]?\d[\d\.\-]+[-\s]?\d\b',
    re.IGNORECASE
)

# Placa de veículo: ABC-1234 ou ABC1D23 (Mercosul)
PLACA = re.compile(
    r'\b[A-Z]{3}[-\s]?\d{4}\b'
    r'|\b[A-Z]{3}\d[A-Z]\d{2}\b'
)

# Título de eleitor
TITULO_ELEITOR = re.compile(
    r'\bt[íi]tulo\s+de\s+eleitor[:\s]?\d[\d\s]+\b',
    re.IGNORECASE
)

# Passaporte
PASSAPORTE = re.compile(
    r'\bpassaporte[:\s]?[A-Z]{2}\d{6}\b'
    r'|\b[A-Z]{2}\d{6}\b',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Padrões contextuais (nomes de partes com contexto)
# ---------------------------------------------------------------------------

# Palavras que precedem nomes de partes em documentos jurídicos
PREFIXOS_PARTE = re.compile(
    r'(?:'
    r'requerente[:\s]+|requerido[:\s]+|autor(?:a)?[:\s]+'
    r'|r[ée]u?[:\s]+|apelante[:\s]+|apelado[:\s]+|recorrente[:\s]+'
    r'|recorrido[:\s]+|impetrante[:\s]+|impetrado[:\s]+'
    r'|exequente[:\s]+|executado[:\s]+|embargante[:\s]+'
    r'|embargado[:\s]+|agravante[:\s]+|agravado[:\s]+'
    r'|parte\s+autora[:\s]+|parte\s+r[ée][:\s]+'
    r'|advogado(?:\(a\))?[:\s]+|adv\.[:\s]+'
    r'|procurador(?:\(a\))?[:\s]+|defensor(?:\(a\))?[:\s]+'
    r'|curador(?:\(a\))?[:\s]+|testemu\w+[:\s]+'
    r'|assistido[:\s]+|representado[:\s]+'
    r')',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Lista de stopwords jurídicas (não são nomes de pessoas)
# ---------------------------------------------------------------------------
STOPWORDS_JURIDICAS = {
    'vara', 'turma', 'câmara', 'seção', 'tribunal', 'juízo', 'juizado',
    'comarca', 'fórum', 'processo', 'autos', 'ação', 'recurso',
    'embargos', 'agravo', 'apelação', 'mandado', 'habeas', 'corpus',
    'injunção', 'sentença', 'acórdão', 'decisão', 'despacho',
    'certidão', 'intimação', 'citação', 'audiência', 'sessão',
    'plenário', 'segunda', 'terceira', 'quarta', 'quinta',
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
    'brasil', 'federal', 'estadual', 'municipal', 'superior',
    'supremo', 'justiça', 'direito', 'código', 'artigo', 'parágrafo',
    'inciso', 'alínea', 'lei', 'decreto', 'resolução', 'portaria',
    'súmula', 'ementa', 'relatório', 'voto', 'ministro', 'desembargador',
    'juiz', 'promotor', 'defensor', 'procurador', 'delegado',
    'perito', 'oficial', 'escrivão', 'cartório', 'secretaria',
}

# ---------------------------------------------------------------------------
# Catálogo de todos os detectores estruturados
# ---------------------------------------------------------------------------
DETECTORES = [
    ('CPF',            CPF),
    ('CNPJ',           CNPJ),
    ('PROCESSO',       PROCESSO),
    ('OAB',            OAB),
    ('EMAIL',          EMAIL),
    ('TELEFONE',       TELEFONE),
    ('CEP',            CEP),
    ('RG',             RG),
    ('PLACA',          PLACA),
    ('MATRICULA',      MATRICULA),
    ('CONTA_BANCARIA', CONTA_BANCARIA),
    ('TITULO_ELEITOR', TITULO_ELEITOR),
    ('PASSAPORTE',     PASSAPORTE),
]
