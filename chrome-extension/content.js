/**
 * Content Script - Extrator de Acórdãos do Sistema Falcão
 * Este script é injetado nas páginas do Sistema Falcão para extrair os acórdãos
 */

(function() {
  'use strict';

  // Estado do extrator
  const extractor = {
    isRunning: false,
    isPaused: false,
    settings: {
      delay: 2000,
      includeMetadata: true,
      consolidate: true,
      format: 'txt'
    },
    currentIndex: 0,
    totalItems: 0,
    extractedData: [],
    consolidatedContent: ''
  };

  // Seletores para elementos da página (podem precisar de ajuste)
  const SELECTORS = {
    // Resultados de busca
    resultList: [
      '.resultado-item',
      '.card-resultado',
      '.document-item',
      '.search-result',
      '.list-group-item',
      'article.resultado',
      '[class*="result"]',
      '[class*="card"]'
    ],

    // Total de resultados
    totalResults: [
      '.total-resultados',
      '.result-count',
      '#total-results',
      '[class*="total"]',
      '[class*="count"]'
    ],

    // Paginação
    pagination: {
      next: [
        'a.next',
        '.pagination .next',
        'button.next-page',
        'a[rel="next"]',
        '.btn-next',
        '[class*="next"]'
      ],
      current: [
        '.pagination .active',
        '.current-page',
        '[class*="page"][class*="active"]'
      ]
    },

    // Dentro de cada resultado
    resultItem: {
      numero: [
        '.numero-processo',
        '.process-number',
        'a[href*="numero"]',
        '[class*="numero"]',
        '[class*="processo"]'
      ],
      ementa: [
        '.ementa',
        '.summary',
        '.resumo',
        '[class*="ementa"]',
        '[class*="resumo"]'
      ],
      relator: [
        '.relator',
        '[class*="relator"]',
        '[class*="magistrado"]'
      ],
      orgaoJulgador: [
        '.orgao-julgador',
        '[class*="orgao"]',
        '[class*="turma"]'
      ],
      dataJulgamento: [
        '.data-julgamento',
        '.data',
        '[class*="data"]'
      ],
      link: [
        'a[href*="inteiro"]',
        'a[href*="documento"]',
        'a.btn-view',
        'a.ver-mais',
        'a[href*="acordao"]'
      ]
    },

    // Página de inteiro teor
    inteiroTeor: [
      '.inteiro-teor',
      '.document-content',
      '.conteudo-documento',
      '#inteiro-teor',
      '.texto-documento',
      'article',
      '.main-content',
      '#conteudo',
      '.content',
      '[class*="teor"]',
      '[class*="conteudo"]'
    ]
  };

  // Inicialização
  init();

  function init() {
    console.log('[Extrator Falcão] Content script carregado');

    // Escutar mensagens do popup
    chrome.runtime.onMessage.addListener(handleMessage);

    // Notificar que o content script está ativo
    sendMessage({ type: 'log', data: { message: 'Content script ativo na página', type: 'info' } });

    // Enviar informações da página
    setTimeout(() => {
      sendPageInfo();
    }, 1000);
  }

  function handleMessage(message, sender, sendResponse) {
    console.log('[Extrator Falcão] Mensagem recebida:', message);

    switch (message.action) {
      case 'getPageInfo':
        sendResponse(getPageInfo());
        break;

      case 'startExtraction':
        extractor.settings = { ...extractor.settings, ...message.settings };
        startExtraction();
        sendResponse({ status: 'started' });
        break;

      case 'pause':
        extractor.isPaused = true;
        sendResponse({ status: 'paused' });
        break;

      case 'resume':
        extractor.isPaused = false;
        continueExtraction();
        sendResponse({ status: 'resumed' });
        break;

      case 'stop':
        extractor.isRunning = false;
        extractor.isPaused = false;
        sendResponse({ status: 'stopped' });
        break;

      case 'getConsolidatedData':
        sendResponse({ data: extractor.consolidatedContent });
        break;

      default:
        sendResponse({ error: 'Ação desconhecida' });
    }

    return true;
  }

  function sendMessage(message) {
    try {
      chrome.runtime.sendMessage(message);
    } catch (error) {
      console.error('[Extrator Falcão] Erro ao enviar mensagem:', error);
    }
  }

  function sendPageInfo() {
    const info = getPageInfo();
    sendMessage({ type: 'pageInfo', data: info });
  }

  function getPageInfo() {
    const info = {
      totalResults: getTotalResults(),
      currentPage: getCurrentPage(),
      hasResults: getResultItems().length > 0
    };

    console.log('[Extrator Falcão] Info da página:', info);
    return info;
  }

  // ==================== Seletores ====================

  function findElement(selectors, context = document) {
    for (const selector of selectors) {
      try {
        const element = context.querySelector(selector);
        if (element) return element;
      } catch (e) {
        // Ignora seletores inválidos
      }
    }
    return null;
  }

  function findElements(selectors, context = document) {
    for (const selector of selectors) {
      try {
        const elements = context.querySelectorAll(selector);
        if (elements.length > 0) return Array.from(elements);
      } catch (e) {
        // Ignora seletores inválidos
      }
    }
    return [];
  }

  function getTotalResults() {
    const element = findElement(SELECTORS.totalResults);
    if (element) {
      const text = element.textContent;
      const match = text.match(/(\d+)/);
      if (match) return parseInt(match[1], 10);
    }

    // Fallback: contar itens na página
    return getResultItems().length;
  }

  function getCurrentPage() {
    const element = findElement(SELECTORS.pagination.current);
    if (element) {
      const text = element.textContent;
      const match = text.match(/(\d+)/);
      if (match) return parseInt(match[1], 10);
    }
    return 1;
  }

  function getResultItems() {
    return findElements(SELECTORS.resultList);
  }

  // ==================== Extração ====================

  async function startExtraction() {
    console.log('[Extrator Falcão] Iniciando extração...');

    extractor.isRunning = true;
    extractor.isPaused = false;
    extractor.currentIndex = 0;
    extractor.extractedData = [];
    extractor.consolidatedContent = generateConsolidatedHeader();

    const items = getResultItems();
    extractor.totalItems = items.length;

    if (items.length === 0) {
      sendMessage({
        type: 'error',
        data: 'Nenhum resultado encontrado na página. Faça uma busca primeiro.'
      });
      extractor.isRunning = false;
      return;
    }

    sendMessage({
      type: 'log',
      data: { message: `Encontrados ${items.length} resultados para extrair`, type: 'info' }
    });

    await processItems(items);
  }

  async function processItems(items) {
    for (let i = extractor.currentIndex; i < items.length; i++) {
      if (!extractor.isRunning) {
        sendMessage({ type: 'log', data: { message: 'Extração interrompida', type: 'warning' } });
        break;
      }

      while (extractor.isPaused) {
        await sleep(500);
        if (!extractor.isRunning) break;
      }

      extractor.currentIndex = i;

      try {
        const acordao = await extractAcordao(items[i], i + 1);

        if (acordao) {
          extractor.extractedData.push(acordao);
          addToConsolidated(acordao, i + 1);

          sendMessage({
            type: 'acordaoExtracted',
            data: acordao
          });
        }

        sendMessage({
          type: 'extractionProgress',
          data: {
            current: i + 1,
            total: items.length,
            currentItem: acordao?.numero || `Item ${i + 1}`
          }
        });

      } catch (error) {
        console.error(`[Extrator Falcão] Erro no item ${i + 1}:`, error);
        sendMessage({
          type: 'error',
          data: `Erro ao extrair item ${i + 1}: ${error.message}`
        });
      }

      // Delay entre extrações
      if (i < items.length - 1) {
        await sleep(extractor.settings.delay);
      }
    }

    // Verificar se há próxima página
    if (extractor.isRunning) {
      const hasNextPage = await goToNextPage();

      if (hasNextPage) {
        // Aguardar a página carregar
        await sleep(3000);
        const newItems = getResultItems();

        if (newItems.length > 0) {
          extractor.currentIndex = 0;
          extractor.totalItems += newItems.length;
          await processItems(newItems);
          return;
        }
      }

      // Extração completa
      finishExtraction();
    }
  }

  async function extractAcordao(item, index) {
    console.log(`[Extrator Falcão] Extraindo item ${index}...`);

    const acordao = {
      numero: '',
      ementa: '',
      relator: '',
      orgaoJulgador: '',
      dataJulgamento: '',
      dataPublicacao: '',
      classe: '',
      url: '',
      inteiroTeor: ''
    };

    // Extrair metadados do card de resultado
    acordao.numero = getTextFromSelectors(SELECTORS.resultItem.numero, item);
    acordao.ementa = getTextFromSelectors(SELECTORS.resultItem.ementa, item);
    acordao.relator = getTextFromSelectors(SELECTORS.resultItem.relator, item);
    acordao.orgaoJulgador = getTextFromSelectors(SELECTORS.resultItem.orgaoJulgador, item);
    acordao.dataJulgamento = getTextFromSelectors(SELECTORS.resultItem.dataJulgamento, item);

    // Procurar link para inteiro teor
    const linkElement = findElement(SELECTORS.resultItem.link, item) || item.querySelector('a');

    if (linkElement) {
      acordao.url = linkElement.href;

      // Tentar extrair inteiro teor
      acordao.inteiroTeor = await fetchInteiroTeor(linkElement.href);
    } else {
      // Se não há link, tentar clicar no item e extrair conteúdo
      acordao.inteiroTeor = await extractViaClick(item);
    }

    // Se não conseguiu extrair nada, usar a ementa
    if (!acordao.inteiroTeor && acordao.ementa) {
      acordao.inteiroTeor = acordao.ementa;
    }

    console.log(`[Extrator Falcão] Item ${index} extraído:`, acordao.numero || 'sem número');

    return acordao;
  }

  function getTextFromSelectors(selectors, context) {
    const element = findElement(selectors, context);
    return element ? element.textContent.trim() : '';
  }

  async function fetchInteiroTeor(url) {
    try {
      const response = await fetch(url);
      if (!response.ok) return '';

      const html = await response.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      // Procurar conteúdo do inteiro teor
      for (const selector of SELECTORS.inteiroTeor) {
        const element = doc.querySelector(selector);
        if (element) {
          const text = element.textContent.trim();
          if (text.length > 100) {
            return cleanText(text);
          }
        }
      }

      // Fallback: pegar o body inteiro (removendo scripts e estilos)
      const body = doc.querySelector('body');
      if (body) {
        // Remover elementos indesejados
        body.querySelectorAll('script, style, nav, header, footer, aside').forEach(el => el.remove());
        return cleanText(body.textContent);
      }

      return '';

    } catch (error) {
      console.error('[Extrator Falcão] Erro ao buscar inteiro teor:', error);
      return '';
    }
  }

  async function extractViaClick(item) {
    try {
      // Abrir em nova aba
      const link = item.querySelector('a');
      if (!link) return '';

      // Criar um link temporário e clicar
      const url = link.href || link.getAttribute('data-href');
      if (!url) return '';

      return await fetchInteiroTeor(url);

    } catch (error) {
      console.error('[Extrator Falcão] Erro na extração via clique:', error);
      return '';
    }
  }

  async function goToNextPage() {
    const nextButton = findElement(SELECTORS.pagination.next);

    if (nextButton && !nextButton.disabled && !nextButton.classList.contains('disabled')) {
      try {
        nextButton.click();
        sendMessage({
          type: 'log',
          data: { message: 'Indo para próxima página...', type: 'info' }
        });
        return true;
      } catch (error) {
        console.error('[Extrator Falcão] Erro ao ir para próxima página:', error);
      }
    }

    return false;
  }

  function finishExtraction() {
    extractor.isRunning = false;

    sendMessage({
      type: 'extractionComplete',
      data: {
        total: extractor.extractedData.length,
        success: extractor.extractedData.length
      }
    });

    sendMessage({
      type: 'log',
      data: {
        message: `Extração finalizada! ${extractor.extractedData.length} acórdãos extraídos.`,
        type: 'success'
      }
    });
  }

  async function continueExtraction() {
    const items = getResultItems();
    if (items.length > 0 && extractor.currentIndex < items.length) {
      await processItems(items);
    }
  }

  // ==================== Arquivo Consolidado ====================

  function generateConsolidatedHeader() {
    const now = new Date();
    return `${'='.repeat(80)}
ACÓRDÃOS - SISTEMA FALCÃO
Extração realizada em: ${now.toLocaleString('pt-BR')}
${'='.repeat(80)}

`;
  }

  function addToConsolidated(acordao, index) {
    let content = `
${'='.repeat(80)}
ACÓRDÃO #${index}
${'='.repeat(80)}

`;

    if (extractor.settings.includeMetadata) {
      if (acordao.numero) content += `NÚMERO DO PROCESSO: ${acordao.numero}\n`;
      if (acordao.relator) content += `RELATOR: ${acordao.relator}\n`;
      if (acordao.orgaoJulgador) content += `ÓRGÃO JULGADOR: ${acordao.orgaoJulgador}\n`;
      if (acordao.dataJulgamento) content += `DATA DE JULGAMENTO: ${acordao.dataJulgamento}\n`;
      if (acordao.url) content += `URL: ${acordao.url}\n`;
      content += `\n${'-'.repeat(40)}\n`;
    }

    if (acordao.ementa) {
      content += `EMENTA:\n${'-'.repeat(40)}\n${acordao.ementa}\n\n`;
    }

    content += `INTEIRO TEOR:\n${'-'.repeat(40)}\n${acordao.inteiroTeor || 'Não disponível'}\n\n`;

    extractor.consolidatedContent += content;
  }

  // ==================== Utilidades ====================

  function cleanText(text) {
    return text
      .replace(/\s+/g, ' ')  // Múltiplos espaços para um
      .replace(/\n\s*\n/g, '\n\n')  // Múltiplas quebras para duas
      .trim();
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Adicionar indicador visual na página
  function addExtractorIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'extrator-falcao-indicator';
    indicator.innerHTML = `
      <style>
        #extrator-falcao-indicator {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: #1a73e8;
          color: white;
          padding: 10px 15px;
          border-radius: 8px;
          font-family: Arial, sans-serif;
          font-size: 12px;
          z-index: 999999;
          box-shadow: 0 2px 10px rgba(0,0,0,0.2);
          display: none;
        }
        #extrator-falcao-indicator.active {
          display: block;
        }
        #extrator-falcao-indicator .spinner {
          display: inline-block;
          width: 12px;
          height: 12px;
          border: 2px solid white;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-right: 8px;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      </style>
      <span class="spinner"></span>
      <span class="text">Extraindo acórdãos...</span>
    `;
    document.body.appendChild(indicator);

    // Atualizar indicador quando extração está ativa
    const updateIndicator = () => {
      const el = document.getElementById('extrator-falcao-indicator');
      if (el) {
        if (extractor.isRunning && !extractor.isPaused) {
          el.classList.add('active');
          el.querySelector('.text').textContent =
            `Extraindo... (${extractor.currentIndex + 1}/${extractor.totalItems})`;
        } else if (extractor.isPaused) {
          el.classList.add('active');
          el.querySelector('.text').textContent = 'Pausado';
        } else {
          el.classList.remove('active');
        }
      }
      requestAnimationFrame(updateIndicator);
    };
    updateIndicator();
  }

  // Adicionar indicador quando DOM estiver pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addExtractorIndicator);
  } else {
    addExtractorIndicator();
  }

})();
