#!/usr/bin/env python3
"""
Ponto de entrada da aplicação Anonimizador Jurídico.
Execute:  python anonimizar.py
"""
import sys
import os

# Garante que o diretório raiz está no path quando executado diretamente
sys.path.insert(0, os.path.dirname(__file__))

from anonimizador.gui import iniciar

if __name__ == '__main__':
    iniciar()
