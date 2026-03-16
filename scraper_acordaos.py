#!/usr/bin/env python3
"""
Scraper para coleta de acórdãos do Sistema Falcão (Justiça do Trabalho)
Filtra por: TRT21, Magistrado Bento Herculano Duarte Neto, Período 2022-2023
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from tqdm import tqdm

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FalcaoScraper:
    """Scraper para o Sistema Falcão de jurisprudência trabalhista."""

    BASE_URL = "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa"

    # Configurações de filtro
    TRIBUNAL = "TRT21"
    MAGISTRADO = "Bento Herculano Duarte Neto"
    DATA_INICIO = "01/01/2022"
    DATA_FIM = "31/12/2023"

    def __init__(self, headless: bool = True, browser: str = "chrome"):
        """
        Inicializa o scraper.

        Args:
            headless: Se True, executa sem interface gráfica
            browser: Navegador a usar ("chrome" ou "firefox")
        """
        self.headless = headless
        self.browser = browser.lower()
        self.driver: Optional[webdriver.Remote] = None
        self.acordaos: list[dict] = []
        self.output_dir = "output"

        # Criar diretório de saída
        os.makedirs(self.output_dir, exist_ok=True)

    def _setup_chrome(self) -> webdriver.Chrome:
        """Configura e retorna driver Chrome."""
        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=pt-BR")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # User agent mais comum
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        if WEBDRIVER_MANAGER_AVAILABLE:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        else:
            return webdriver.Chrome(options=options)

    def _setup_firefox(self) -> webdriver.Firefox:
        """Configura e retorna driver Firefox."""
        options = FirefoxOptions()
        if self.headless:
            options.add_argument("--headless")
        options.set_preference("intl.accept_languages", "pt-BR")

        if WEBDRIVER_MANAGER_AVAILABLE:
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        else:
            return webdriver.Firefox(options=options)

    def start_driver(self):
        """Inicia o driver do navegador."""
        logger.info(f"Iniciando navegador {self.browser} (headless={self.headless})")

        if self.browser == "chrome":
            self.driver = self._setup_chrome()
        elif self.browser == "firefox":
            self.driver = self._setup_firefox()
        else:
            raise ValueError(f"Navegador não suportado: {self.browser}")

        self.driver.implicitly_wait(10)
        logger.info("Navegador iniciado com sucesso")

    def stop_driver(self):
        """Encerra o driver do navegador."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Navegador encerrado")

    def wait_for_element(self, by: By, value: str, timeout: int = 30) -> bool:
        """Aguarda elemento estar presente na página."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False

    def wait_for_clickable(self, by: By, value: str, timeout: int = 30):
        """Aguarda elemento estar clicável."""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def safe_click(self, element, retries: int = 3):
        """Clica em elemento com tratamento de erros."""
        for attempt in range(retries):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                element.click()
                return True
            except ElementClickInterceptedException:
                time.sleep(1)
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    pass
            except StaleElementReferenceException:
                time.sleep(1)
        return False

    def navigate_to_search(self):
        """Navega para a página de pesquisa."""
        logger.info(f"Acessando: {self.BASE_URL}")
        self.driver.get(self.BASE_URL)
        time.sleep(3)

        # Aguarda a página carregar
        if not self.wait_for_element(By.TAG_NAME, "body", timeout=30):
            raise Exception("Falha ao carregar página inicial")

        logger.info("Página de pesquisa carregada")

    def execute_empty_search(self):
        """Executa pesquisa com termo vazio para listar todos os documentos."""
        logger.info("Executando pesquisa com termo vazio...")

        # Procura o botão de pesquisa e clica
        try:
            # Tenta encontrar o campo de pesquisa
            search_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='search'], input[type='text'], #pesquisa, .search-input")
            search_input.clear()

            # Pressiona Enter para buscar
            search_input.send_keys(Keys.RETURN)
            time.sleep(3)

        except NoSuchElementException:
            # Se não encontrar campo de pesquisa, tenta clicar no botão diretamente
            try:
                search_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn-search, #btn-pesquisar")
                self.safe_click(search_btn)
                time.sleep(3)
            except NoSuchElementException:
                logger.warning("Não encontrou campo/botão de pesquisa, tentando continuar...")

        logger.info("Pesquisa executada")

    def apply_tribunal_filter(self):
        """Aplica filtro de Tribunal (TRT21)."""
        logger.info(f"Aplicando filtro de Tribunal: {self.TRIBUNAL}")

        try:
            # Procura por filtros de tribunal
            # O site pode usar diferentes seletores
            filter_selectors = [
                f"//label[contains(text(), '{self.TRIBUNAL}')]",
                f"//span[contains(text(), '{self.TRIBUNAL}')]",
                f"//input[@value='{self.TRIBUNAL}']",
                f"//div[contains(@class, 'filtro')]//label[contains(text(), 'TRT21')]",
                f"//a[contains(text(), '{self.TRIBUNAL}')]",
            ]

            for selector in filter_selectors:
                try:
                    element = self.driver.find_element(By.XPATH, selector)
                    self.safe_click(element)
                    logger.info(f"Filtro de tribunal aplicado via: {selector}")
                    time.sleep(2)
                    return True
                except NoSuchElementException:
                    continue

            # Tenta via dropdown/select
            try:
                tribunal_dropdown = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "select[name*='tribunal'], select#tribunal, .tribunal-select"
                )
                from selenium.webdriver.support.ui import Select
                select = Select(tribunal_dropdown)
                select.select_by_visible_text(self.TRIBUNAL)
                time.sleep(2)
                return True
            except NoSuchElementException:
                pass

            logger.warning("Não foi possível aplicar filtro de tribunal automaticamente")
            return False

        except Exception as e:
            logger.error(f"Erro ao aplicar filtro de tribunal: {e}")
            return False

    def apply_magistrado_filter(self):
        """Aplica filtro de Magistrado."""
        logger.info(f"Aplicando filtro de Magistrado: {self.MAGISTRADO}")

        try:
            # Procura por filtros de magistrado
            filter_selectors = [
                f"//label[contains(text(), '{self.MAGISTRADO}')]",
                f"//span[contains(text(), '{self.MAGISTRADO}')]",
                f"//option[contains(text(), '{self.MAGISTRADO}')]",
                f"//a[contains(text(), 'Bento')]",
            ]

            for selector in filter_selectors:
                try:
                    element = self.driver.find_element(By.XPATH, selector)
                    self.safe_click(element)
                    logger.info(f"Filtro de magistrado aplicado via: {selector}")
                    time.sleep(2)
                    return True
                except NoSuchElementException:
                    continue

            # Tenta via input de texto/autocomplete
            try:
                magistrado_input = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "input[name*='magistrado'], input#magistrado, input[placeholder*='magistrado']"
                )
                magistrado_input.clear()
                magistrado_input.send_keys(self.MAGISTRADO)
                time.sleep(2)

                # Tenta clicar na sugestão
                try:
                    suggestion = self.driver.find_element(
                        By.XPATH,
                        f"//li[contains(text(), '{self.MAGISTRADO}')]"
                    )
                    self.safe_click(suggestion)
                except NoSuchElementException:
                    magistrado_input.send_keys(Keys.RETURN)

                time.sleep(2)
                return True
            except NoSuchElementException:
                pass

            logger.warning("Não foi possível aplicar filtro de magistrado automaticamente")
            return False

        except Exception as e:
            logger.error(f"Erro ao aplicar filtro de magistrado: {e}")
            return False

    def apply_period_filter(self):
        """Aplica filtro de período (01/01/2022 a 31/12/2023)."""
        logger.info(f"Aplicando filtro de período: {self.DATA_INICIO} a {self.DATA_FIM}")

        try:
            # Procura campos de data
            date_start_selectors = [
                "input[name*='dataInicio']",
                "input[name*='data_inicio']",
                "input#dataInicio",
                "input[placeholder*='Início']",
                "input.data-inicio",
            ]

            date_end_selectors = [
                "input[name*='dataFim']",
                "input[name*='data_fim']",
                "input#dataFim",
                "input[placeholder*='Final']",
                "input.data-fim",
            ]

            # Tenta encontrar e preencher campo de data início
            for selector in date_start_selectors:
                try:
                    date_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                    date_input.clear()
                    date_input.send_keys(self.DATA_INICIO)
                    logger.info(f"Data início preenchida via: {selector}")
                    break
                except NoSuchElementException:
                    continue

            # Tenta encontrar e preencher campo de data fim
            for selector in date_end_selectors:
                try:
                    date_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                    date_input.clear()
                    date_input.send_keys(self.DATA_FIM)
                    logger.info(f"Data fim preenchida via: {selector}")
                    break
                except NoSuchElementException:
                    continue

            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"Erro ao aplicar filtro de período: {e}")
            return False

    def get_total_results(self) -> int:
        """Obtém o número total de resultados."""
        try:
            # Procura por indicadores de total de resultados
            result_selectors = [
                ".total-resultados",
                ".result-count",
                "#total-results",
                "//span[contains(text(), 'resultado')]",
                "//div[contains(text(), 'encontrado')]",
            ]

            for selector in result_selectors:
                try:
                    if selector.startswith("//"):
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    text = element.text
                    # Extrai números do texto
                    import re
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        return int(numbers[0])
                except NoSuchElementException:
                    continue

            return 0

        except Exception as e:
            logger.error(f"Erro ao obter total de resultados: {e}")
            return 0

    def get_result_items(self) -> list:
        """Obtém lista de itens de resultado na página atual."""
        try:
            # Procura por cards/items de resultado
            item_selectors = [
                ".resultado-item",
                ".card-resultado",
                ".document-item",
                ".search-result",
                "article.resultado",
                ".list-group-item",
            ]

            for selector in item_selectors:
                try:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if items:
                        return items
                except NoSuchElementException:
                    continue

            # Tenta via XPath genérico
            try:
                items = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class, 'result') or contains(@class, 'card')]"
                )
                if items:
                    return items
            except NoSuchElementException:
                pass

            return []

        except Exception as e:
            logger.error(f"Erro ao obter itens de resultado: {e}")
            return []

    def extract_acordao_info(self, item) -> dict:
        """Extrai informações básicas de um item de resultado."""
        info = {
            "numero_processo": "",
            "ementa": "",
            "orgao_julgador": "",
            "relator": "",
            "data_julgamento": "",
            "data_publicacao": "",
            "classe": "",
            "inteiro_teor": "",
            "url": "",
        }

        try:
            # Tenta extrair número do processo
            try:
                numero_elem = item.find_element(
                    By.CSS_SELECTOR,
                    ".numero-processo, .process-number, a[href*='numero']"
                )
                info["numero_processo"] = numero_elem.text.strip()
            except NoSuchElementException:
                pass

            # Tenta extrair ementa
            try:
                ementa_elem = item.find_element(
                    By.CSS_SELECTOR,
                    ".ementa, .summary, .resumo"
                )
                info["ementa"] = ementa_elem.text.strip()
            except NoSuchElementException:
                pass

            # Tenta extrair link para inteiro teor
            try:
                link_elem = item.find_element(By.CSS_SELECTOR, "a[href*='inteiro'], a.btn-view")
                info["url"] = link_elem.get_attribute("href")
            except NoSuchElementException:
                try:
                    link_elem = item.find_element(By.TAG_NAME, "a")
                    info["url"] = link_elem.get_attribute("href")
                except NoSuchElementException:
                    pass

        except Exception as e:
            logger.error(f"Erro ao extrair info do acórdão: {e}")

        return info

    def extract_inteiro_teor(self, url: str) -> str:
        """Acessa página do acórdão e extrai inteiro teor."""
        if not url:
            return ""

        try:
            # Abre em nova aba
            self.driver.execute_script(f"window.open('{url}', '_blank');")
            time.sleep(2)

            # Muda para nova aba
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(3)

            inteiro_teor = ""

            # Procura pelo conteúdo do inteiro teor
            teor_selectors = [
                ".inteiro-teor",
                ".document-content",
                ".conteudo-documento",
                "#inteiro-teor",
                ".texto-documento",
                "article",
                ".main-content",
            ]

            for selector in teor_selectors:
                try:
                    teor_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    inteiro_teor = teor_elem.text.strip()
                    if inteiro_teor and len(inteiro_teor) > 100:
                        break
                except NoSuchElementException:
                    continue

            # Se não encontrou, tenta pegar o body inteiro
            if not inteiro_teor or len(inteiro_teor) < 100:
                try:
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    inteiro_teor = body.text.strip()
                except NoSuchElementException:
                    pass

            # Fecha a aba e volta para a principal
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            return inteiro_teor

        except Exception as e:
            logger.error(f"Erro ao extrair inteiro teor de {url}: {e}")
            # Garante que volta para aba principal
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception:
                pass
            return ""

    def go_to_next_page(self) -> bool:
        """Navega para próxima página de resultados."""
        try:
            next_selectors = [
                "a.next",
                ".pagination .next",
                "button.next-page",
                "//a[contains(text(), 'Próxim')]",
                "//a[contains(text(), '›')]",
                "//button[contains(text(), 'Próxim')]",
            ]

            for selector in next_selectors:
                try:
                    if selector.startswith("//"):
                        next_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        next_btn = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if next_btn.is_enabled():
                        self.safe_click(next_btn)
                        time.sleep(3)
                        return True
                except NoSuchElementException:
                    continue

            return False

        except Exception as e:
            logger.error(f"Erro ao navegar para próxima página: {e}")
            return False

    def save_acordaos(self):
        """Salva acórdãos coletados em arquivos."""
        if not self.acordaos:
            logger.warning("Nenhum acórdão para salvar")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Salva JSON com todos os dados
        json_path = os.path.join(self.output_dir, f"acordaos_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.acordaos, f, ensure_ascii=False, indent=2)
        logger.info(f"Acórdãos salvos em JSON: {json_path}")

        # Salva arquivo texto consolidado com inteiro teor
        txt_path = os.path.join(self.output_dir, f"acordaos_inteiro_teor_{timestamp}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ACÓRDÃOS - DESEMBARGADOR BENTO HERCULANO DUARTE NETO\n")
            f.write(f"TRT21 - Período: {self.DATA_INICIO} a {self.DATA_FIM}\n")
            f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Total de acórdãos: {len(self.acordaos)}\n")
            f.write("=" * 80 + "\n\n")

            for i, acordao in enumerate(self.acordaos, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"ACÓRDÃO #{i}\n")
                f.write(f"{'=' * 80}\n\n")

                if acordao.get("numero_processo"):
                    f.write(f"Número do Processo: {acordao['numero_processo']}\n")
                if acordao.get("classe"):
                    f.write(f"Classe: {acordao['classe']}\n")
                if acordao.get("relator"):
                    f.write(f"Relator: {acordao['relator']}\n")
                if acordao.get("orgao_julgador"):
                    f.write(f"Órgão Julgador: {acordao['orgao_julgador']}\n")
                if acordao.get("data_julgamento"):
                    f.write(f"Data de Julgamento: {acordao['data_julgamento']}\n")
                if acordao.get("data_publicacao"):
                    f.write(f"Data de Publicação: {acordao['data_publicacao']}\n")
                if acordao.get("url"):
                    f.write(f"URL: {acordao['url']}\n")

                f.write(f"\n{'-' * 40}\n")
                f.write("EMENTA:\n")
                f.write(f"{'-' * 40}\n")
                f.write(f"{acordao.get('ementa', 'N/A')}\n")

                f.write(f"\n{'-' * 40}\n")
                f.write("INTEIRO TEOR:\n")
                f.write(f"{'-' * 40}\n")
                f.write(f"{acordao.get('inteiro_teor', 'N/A')}\n")

                f.write("\n")

        logger.info(f"Inteiro teor consolidado salvo em: {txt_path}")

        # Salva CSV para fácil análise
        try:
            import pandas as pd
            csv_path = os.path.join(self.output_dir, f"acordaos_{timestamp}.csv")
            df = pd.DataFrame(self.acordaos)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"Dados salvos em CSV: {csv_path}")
        except ImportError:
            logger.warning("Pandas não disponível, CSV não gerado")

    def run(self, max_pages: int = 100, extract_full_text: bool = True):
        """
        Executa o processo completo de scraping.

        Args:
            max_pages: Número máximo de páginas a processar
            extract_full_text: Se True, extrai inteiro teor de cada acórdão
        """
        try:
            self.start_driver()
            self.navigate_to_search()

            # Executa pesquisa vazia
            self.execute_empty_search()

            # Aplica filtros
            self.apply_tribunal_filter()
            time.sleep(2)

            self.apply_magistrado_filter()
            time.sleep(2)

            self.apply_period_filter()
            time.sleep(2)

            # Aguarda resultados carregarem
            time.sleep(5)

            total = self.get_total_results()
            logger.info(f"Total de resultados encontrados: {total}")

            # Processa páginas de resultados
            page = 1
            while page <= max_pages:
                logger.info(f"Processando página {page}...")

                items = self.get_result_items()
                if not items:
                    logger.info("Nenhum item encontrado, finalizando")
                    break

                logger.info(f"Encontrados {len(items)} itens na página {page}")

                for item in tqdm(items, desc=f"Página {page}"):
                    try:
                        info = self.extract_acordao_info(item)

                        if extract_full_text and info.get("url"):
                            info["inteiro_teor"] = self.extract_inteiro_teor(info["url"])
                            time.sleep(1)  # Delay para não sobrecarregar o servidor

                        if info.get("numero_processo") or info.get("inteiro_teor"):
                            self.acordaos.append(info)

                    except Exception as e:
                        logger.error(f"Erro ao processar item: {e}")
                        continue

                # Salva progresso parcial
                if page % 5 == 0:
                    self.save_acordaos()

                # Tenta ir para próxima página
                if not self.go_to_next_page():
                    logger.info("Não há mais páginas, finalizando")
                    break

                page += 1

            # Salva resultado final
            self.save_acordaos()

            logger.info(f"Scraping finalizado. Total de acórdãos coletados: {len(self.acordaos)}")

        except Exception as e:
            logger.error(f"Erro durante execução: {e}")
            raise
        finally:
            self.stop_driver()


def main():
    """Função principal."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scraper de acórdãos do Sistema Falcão"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Executa com interface gráfica (útil para debug)"
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "firefox"],
        default="chrome",
        help="Navegador a utilizar (padrão: chrome)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Número máximo de páginas a processar (padrão: 100)"
    )
    parser.add_argument(
        "--skip-full-text",
        action="store_true",
        help="Não extrai inteiro teor (apenas dados básicos)"
    )

    args = parser.parse_args()

    scraper = FalcaoScraper(
        headless=not args.no_headless,
        browser=args.browser
    )

    scraper.run(
        max_pages=args.max_pages,
        extract_full_text=not args.skip_full_text
    )


if __name__ == "__main__":
    main()
