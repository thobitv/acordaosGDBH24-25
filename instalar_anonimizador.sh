#!/bin/bash
# Instalação das dependências do Anonimizador Jurídico
# Resolução CNJ n. 615/2024

set -e

echo "=========================================="
echo " Anonimizador de Documentos Jurídicos"
echo " Instalação de dependências"
echo "=========================================="

pip install "pymupdf>=1.23.0" "spacy>=3.7.0"

echo ""
echo "Baixando modelo de linguagem spaCy para português (pt_core_news_lg)..."
python -m spacy download pt_core_news_lg

echo ""
echo "=========================================="
echo " Instalação concluída!"
echo " Execute: python anonimizar.py"
echo "=========================================="
