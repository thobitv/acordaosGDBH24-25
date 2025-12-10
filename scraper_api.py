#!/usr/bin/env python3
"""
Scraper alternativo usando API interna do Sistema Falcão
Tenta descobrir e usar endpoints REST/Elasticsearch diretamente
"""

import os
import json
import time
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FalcaoAPIClient:
    """Cliente para acessar API do Sistema Falcão."""

    BASE_URL = "https://jurisprudencia.jt.jus.br"
    SEARCH_URL = f"{BASE_URL}/jurisprudencia-nacional/pesquisa"

    # Possíveis endpoints de API (baseado em padrões comuns)
    API_ENDPOINTS = [
        "/api/v1/documentos",
        "/api/v1/acordaos",
        "/api/v1/pesquisa",
        "/api/documentos/search",
        "/api/search",
        "/jurisprudencia-nacional/api/search",
        "/jurisprudencia-nacional/api/documentos",
        "/rest/api/search",
        "/elasticsearch/_search",
    ]

    # Configurações de filtro
    TRIBUNAL = "TRT21"
    MAGISTRADO = "Bento Herculano Duarte Neto"
    DATA_INICIO = "2024-01-01"
    DATA_FIM = "2025-07-04"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        self.acordaos = []
        self.output_dir = "output"
        self.api_endpoint = None

        os.makedirs(self.output_dir, exist_ok=True)

    def discover_api_endpoint(self) -> Optional[str]:
        """Tenta descobrir o endpoint da API."""
        logger.info("Tentando descobrir endpoint da API...")

        # Primeiro, acessa a página principal para obter cookies
        try:
            response = self.session.get(self.SEARCH_URL, timeout=30)
            logger.info(f"Página principal: status {response.status_code}")

            # Analisa o HTML para encontrar endpoints
            soup = BeautifulSoup(response.text, 'lxml')

            # Procura por scripts que possam conter URLs de API
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Procura por URLs de API no código
                    api_patterns = [
                        r'api["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'endpoint["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'baseUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'["\']/(api/[^"\']+)["\']',
                    ]
                    for pattern in api_patterns:
                        matches = re.findall(pattern, script.string, re.IGNORECASE)
                        for match in matches:
                            logger.info(f"Possível endpoint encontrado: {match}")

        except Exception as e:
            logger.error(f"Erro ao acessar página principal: {e}")

        # Testa endpoints conhecidos
        for endpoint in self.API_ENDPOINTS:
            url = urljoin(self.BASE_URL, endpoint)
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code in [200, 401, 403]:
                    logger.info(f"Endpoint válido encontrado: {url} (status: {response.status_code})")
                    if response.status_code == 200:
                        self.api_endpoint = url
                        return url
            except Exception:
                continue

        return None

    def search_via_web(self, page: int = 1) -> dict:
        """Faz pesquisa via interface web e parseia resultados."""
        logger.info(f"Buscando via web, página {page}...")

        # Monta URL de pesquisa com filtros
        # Baseado no padrão comum de sistemas de jurisprudência
        params = {
            "tribunal": self.TRIBUNAL,
            "magistrado": self.MAGISTRADO,
            "dataInicio": self.DATA_INICIO,
            "dataFim": self.DATA_FIM,
            "pagina": page,
            "tamanhoPagina": 20,
        }

        try:
            # Tenta diferentes formatos de URL
            search_urls = [
                f"{self.SEARCH_URL}?tribunal={self.TRIBUNAL}&magistrado={quote(self.MAGISTRADO)}&dataInicio={self.DATA_INICIO}&dataFim={self.DATA_FIM}&pagina={page}",
                f"{self.BASE_URL}/jurisprudencia-nacional/api/acordaos?tribunal={self.TRIBUNAL}&relator={quote(self.MAGISTRADO)}&dataInicio={self.DATA_INICIO}&dataFim={self.DATA_FIM}&page={page}",
            ]

            for url in search_urls:
                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200:
                        # Tenta parsear como JSON
                        try:
                            return response.json()
                        except json.JSONDecodeError:
                            # Se não for JSON, parseia HTML
                            return self._parse_html_results(response.text)
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Erro na busca web: {e}")

        return {"items": [], "total": 0}

    def _parse_html_results(self, html: str) -> dict:
        """Parseia resultados HTML."""
        soup = BeautifulSoup(html, 'lxml')
        items = []

        # Procura por cards de resultado
        result_selectors = [
            ".resultado-item",
            ".card-resultado",
            ".document-item",
            ".search-result",
            "article",
            ".list-group-item",
        ]

        for selector in result_selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements:
                    item = self._extract_item_from_html(elem)
                    if item:
                        items.append(item)
                break

        # Tenta extrair total de resultados
        total = 0
        total_elem = soup.select_one(".total-resultados, .result-count, #total-results")
        if total_elem:
            numbers = re.findall(r'\d+', total_elem.text)
            if numbers:
                total = int(numbers[0])

        return {"items": items, "total": total}

    def _extract_item_from_html(self, elem) -> Optional[dict]:
        """Extrai informações de um elemento HTML."""
        try:
            item = {
                "numero_processo": "",
                "ementa": "",
                "relator": "",
                "orgao_julgador": "",
                "data_julgamento": "",
                "data_publicacao": "",
                "classe": "",
                "url": "",
                "inteiro_teor": "",
            }

            # Procura número do processo
            numero_elem = elem.select_one(".numero-processo, .process-number, a[href*='numero']")
            if numero_elem:
                item["numero_processo"] = numero_elem.text.strip()

            # Procura ementa
            ementa_elem = elem.select_one(".ementa, .summary, .resumo")
            if ementa_elem:
                item["ementa"] = ementa_elem.text.strip()

            # Procura link
            link_elem = elem.select_one("a[href*='inteiro'], a[href*='documento'], a.btn-view")
            if link_elem:
                href = link_elem.get("href", "")
                if href:
                    item["url"] = urljoin(self.BASE_URL, href)
            else:
                link_elem = elem.select_one("a")
                if link_elem:
                    href = link_elem.get("href", "")
                    if href:
                        item["url"] = urljoin(self.BASE_URL, href)

            return item if item["numero_processo"] or item["url"] else None

        except Exception as e:
            logger.error(f"Erro ao extrair item: {e}")
            return None

    def get_inteiro_teor(self, url: str) -> str:
        """Obtém inteiro teor de um documento."""
        if not url:
            return ""

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return ""

            soup = BeautifulSoup(response.text, 'lxml')

            # Procura pelo conteúdo principal
            content_selectors = [
                ".inteiro-teor",
                ".document-content",
                ".conteudo-documento",
                "#inteiro-teor",
                ".texto-documento",
                "article",
                ".main-content",
                "#conteudo",
            ]

            for selector in content_selectors:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(separator="\n", strip=True)
                    if text and len(text) > 100:
                        return text

            # Se não encontrou, pega o body
            body = soup.select_one("body")
            if body:
                # Remove scripts e estilos
                for tag in body.select("script, style, nav, header, footer"):
                    tag.decompose()
                return body.get_text(separator="\n", strip=True)

            return ""

        except Exception as e:
            logger.error(f"Erro ao obter inteiro teor de {url}: {e}")
            return ""

    def search_via_api_post(self) -> dict:
        """Tenta busca via POST em possíveis endpoints de API."""
        logger.info("Tentando busca via API POST...")

        # Corpo da requisição em diferentes formatos
        payloads = [
            # Formato Elasticsearch
            {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"tribunal": self.TRIBUNAL}},
                            {"match": {"relator": self.MAGISTRADO}},
                        ],
                        "filter": {
                            "range": {
                                "dataJulgamento": {
                                    "gte": self.DATA_INICIO,
                                    "lte": self.DATA_FIM
                                }
                            }
                        }
                    }
                },
                "size": 100
            },
            # Formato REST simples
            {
                "tribunal": self.TRIBUNAL,
                "magistrado": self.MAGISTRADO,
                "dataInicio": self.DATA_INICIO,
                "dataFim": self.DATA_FIM,
                "tipo": "acordao",
                "page": 1,
                "size": 100
            },
            # Formato alternativo
            {
                "filtros": {
                    "tribunal": [self.TRIBUNAL],
                    "relator": [self.MAGISTRADO],
                    "periodo": {
                        "inicio": self.DATA_INICIO,
                        "fim": self.DATA_FIM
                    }
                },
                "paginacao": {
                    "pagina": 1,
                    "tamanho": 100
                }
            }
        ]

        api_endpoints = [
            f"{self.BASE_URL}/api/search",
            f"{self.BASE_URL}/api/v1/acordaos/search",
            f"{self.BASE_URL}/api/documentos/search",
            f"{self.BASE_URL}/jurisprudencia-nacional/api/search",
        ]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for endpoint in api_endpoints:
            for payload in payloads:
                try:
                    response = self.session.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if data:
                                logger.info(f"API encontrada: {endpoint}")
                                return data
                        except json.JSONDecodeError:
                            continue
                except Exception:
                    continue

        return {"items": [], "total": 0}

    def save_acordaos(self):
        """Salva acórdãos coletados."""
        if not self.acordaos:
            logger.warning("Nenhum acórdão para salvar")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_path = os.path.join(self.output_dir, f"acordaos_api_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.acordaos, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON salvo: {json_path}")

        # Texto consolidado
        txt_path = os.path.join(self.output_dir, f"acordaos_inteiro_teor_api_{timestamp}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ACÓRDÃOS - DESEMBARGADOR BENTO HERCULANO DUARTE NETO\n")
            f.write(f"TRT21 - Período: 01/01/2024 a 04/07/2025\n")
            f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Total de acórdãos: {len(self.acordaos)}\n")
            f.write("=" * 80 + "\n\n")

            for i, acordao in enumerate(self.acordaos, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"ACÓRDÃO #{i}\n")
                f.write(f"{'=' * 80}\n\n")

                for key in ["numero_processo", "classe", "relator", "orgao_julgador",
                           "data_julgamento", "data_publicacao", "url"]:
                    if acordao.get(key):
                        f.write(f"{key.replace('_', ' ').title()}: {acordao[key]}\n")

                f.write(f"\n{'-' * 40}\nEMENTA:\n{'-' * 40}\n")
                f.write(f"{acordao.get('ementa', 'N/A')}\n")

                f.write(f"\n{'-' * 40}\nINTEIRO TEOR:\n{'-' * 40}\n")
                f.write(f"{acordao.get('inteiro_teor', 'N/A')}\n\n")

        logger.info(f"Texto consolidado salvo: {txt_path}")

    def run(self, max_pages: int = 50):
        """Executa coleta de acórdãos."""
        logger.info("Iniciando coleta de acórdãos via API...")

        # Tenta descobrir API
        self.discover_api_endpoint()

        # Tenta busca via API POST
        api_results = self.search_via_api_post()
        if api_results.get("items"):
            logger.info(f"Encontrados {len(api_results['items'])} via API")
            self.acordaos.extend(api_results["items"])

        # Se não funcionou, tenta via web scraping
        if not self.acordaos:
            logger.info("API não disponível, usando web scraping...")

            for page in tqdm(range(1, max_pages + 1), desc="Páginas"):
                results = self.search_via_web(page)

                if not results.get("items"):
                    logger.info(f"Sem mais resultados na página {page}")
                    break

                for item in results["items"]:
                    if item.get("url"):
                        item["inteiro_teor"] = self.get_inteiro_teor(item["url"])
                        time.sleep(1)  # Delay entre requisições

                    self.acordaos.append(item)

                # Salva progresso parcial
                if page % 5 == 0:
                    self.save_acordaos()

        # Extrai inteiro teor se necessário
        logger.info("Extraindo inteiro teor...")
        for acordao in tqdm(self.acordaos, desc="Inteiro teor"):
            if not acordao.get("inteiro_teor") and acordao.get("url"):
                acordao["inteiro_teor"] = self.get_inteiro_teor(acordao["url"])
                time.sleep(1)

        self.save_acordaos()
        logger.info(f"Coleta finalizada. Total: {len(self.acordaos)} acórdãos")


def main():
    """Função principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Scraper via API do Sistema Falcão")
    parser.add_argument("--max-pages", type=int, default=50, help="Máximo de páginas")

    args = parser.parse_args()

    client = FalcaoAPIClient()
    client.run(max_pages=args.max_pages)


if __name__ == "__main__":
    main()
