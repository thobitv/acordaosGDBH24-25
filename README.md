# Extrator de Acórdãos - Sistema Falcão

Este projeto automatiza a coleta de acórdãos do [Sistema Falcão](https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa) da Justiça do Trabalho, com filtros específicos para:

- **Tribunal:** TRT21 (Rio Grande do Norte)
- **Magistrado:** Bento Herculano Duarte Neto
- **Período:** 01/01/2024 a 04/07/2025

## Opções Disponíveis

Este projeto oferece **duas abordagens** para extrair os acórdãos:

| Abordagem | Descrição | Quando Usar |
|-----------|-----------|-------------|
| **Extensão Chrome** | Você faz login e busca, a extensão extrai e salva no Google Drive | Recomendado - mais confiável |
| **Scripts Python** | Automação completa via Selenium ou Requests | Para desenvolvedores |

---

## Opção 1: Extensão Chrome (Recomendado)

A extensão do Chrome permite que você:
1. Faça login manualmente no Sistema Falcão
2. Realize a busca com os filtros desejados
3. Clique em "Iniciar Extração" na extensão
4. Os acórdãos são salvos automaticamente no seu Google Drive

### Instalação Rápida

1. Abra `chrome://extensions/` no Chrome
2. Ative o "Modo do desenvolvedor"
3. Clique em "Carregar sem compactação"
4. Selecione a pasta `chrome-extension/`

**Documentação completa:** [chrome-extension/README.md](chrome-extension/README.md)

### Configuração do Google Drive

Você precisará criar credenciais OAuth no Google Cloud Console. Siga as instruções detalhadas no [README da extensão](chrome-extension/README.md#passo-1-configurar-google-cloud-console).

---

## Opção 2: Scripts Python

## Requisitos

- Python 3.8+
- Chrome ou Firefox instalado (para o scraper com Selenium)

## Instalação

```bash
# Clone ou acesse o repositório
cd acordaosGDBH24-25

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt
```

## Scripts Disponíveis

### 1. `scraper_acordaos.py` (Selenium - Recomendado)

Usa Selenium para automatizar o navegador e interagir com a interface web do sistema.

```bash
# Execução padrão (headless, Chrome)
python scraper_acordaos.py

# Com interface gráfica (útil para debug)
python scraper_acordaos.py --no-headless

# Usando Firefox
python scraper_acordaos.py --browser firefox

# Limitar número de páginas
python scraper_acordaos.py --max-pages 10

# Não extrair inteiro teor (mais rápido)
python scraper_acordaos.py --skip-full-text
```

**Parâmetros:**
- `--no-headless`: Executa com interface gráfica visível
- `--browser [chrome|firefox]`: Escolhe o navegador
- `--max-pages N`: Limita o número de páginas processadas
- `--skip-full-text`: Não extrai o inteiro teor (apenas metadados)

### 2. `scraper_api.py` (Requests - Alternativo)

Tenta usar a API interna do sistema ou fazer scraping via requests.

```bash
python scraper_api.py

# Com limite de páginas
python scraper_api.py --max-pages 30
```

## Arquivos de Saída

Todos os arquivos são salvos na pasta `output/`:

| Arquivo | Descrição |
|---------|-----------|
| `acordaos_YYYYMMDD_HHMMSS.json` | Dados estruturados em JSON |
| `acordaos_inteiro_teor_YYYYMMDD_HHMMSS.txt` | Documento consolidado com inteiro teor |
| `acordaos_YYYYMMDD_HHMMSS.csv` | Dados em formato CSV (se pandas estiver instalado) |
| `scraper.log` | Log de execução |

## Estrutura dos Dados

Cada acórdão coletado contém:

```json
{
  "numero_processo": "0000123-45.2024.5.21.0001",
  "ementa": "Texto da ementa...",
  "relator": "Bento Herculano Duarte Neto",
  "orgao_julgador": "1ª Turma",
  "data_julgamento": "15/03/2024",
  "data_publicacao": "20/03/2024",
  "classe": "Recurso Ordinário",
  "url": "https://...",
  "inteiro_teor": "Texto completo do acórdão..."
}
```

## Uso Manual do Site

Se o scraper não funcionar, você pode usar o site manualmente:

1. Acesse: https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa
2. Deixe o campo de pesquisa em branco e clique em buscar
3. Aplique os filtros:
   - **Tribunal:** TRT21
   - **Magistrada/Magistrado:** Bento Herculano Duarte Neto
   - **Selecionar período:** Início: 01/01/2024 | Final: 04/07/2025
4. Navegue pelos resultados e clique em cada acórdão para ver o inteiro teor

## Dicas de Pesquisa no Site

O site aceita os seguintes operadores:

| Operador | Exemplo | Descrição |
|----------|---------|-----------|
| Espaço | `horas extras` | Busca "horas" OU "extras" |
| Aspas | `"horas extras"` | Busca termo exato |
| + | `+jornada` | Termo obrigatório |
| - | `-jornada` | Termo não deve existir |
| Número CNJ | `0000000-00.0000.0.00.0000` | Busca por número do processo |

## Solução de Problemas

### Erro de WebDriver

```bash
# Instale o webdriver-manager para gerenciar drivers automaticamente
pip install webdriver-manager

# Ou instale o ChromeDriver manualmente
# Ubuntu/Debian:
sudo apt-get install chromium-chromedriver
```

### Site bloqueando requisições

O site pode bloquear requisições automatizadas. Tente:

1. Usar o modo não-headless: `--no-headless`
2. Aumentar os delays no código
3. Usar VPN ou mudar IP
4. Fazer login com conta gov.br (manual)

### Timeout ou página não carrega

Verifique sua conexão e tente:
- Aumentar timeouts no código
- Executar em horários de menor tráfego

## Limitações

- Usuários não autenticados podem visualizar até 200 documentos
- O site pode implementar proteções anti-scraping
- A estrutura do site pode mudar, quebrando os seletores

## Licença

Este projeto é para uso educacional e de pesquisa.

---

**Nota:** Este scraper foi criado para automatizar tarefas legítimas de coleta de jurisprudência pública. Use de forma responsável e respeite os termos de uso do site.
