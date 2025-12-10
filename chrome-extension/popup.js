/**
 * Popup Script - Extrator de Acórdãos do Sistema Falcão
 */

// Estado da aplicação
const state = {
  isConnectedToDrive: false,
  isOnFalcaoPage: false,
  isExtracting: false,
  isPaused: false,
  accessToken: null,
  folderId: null,
  stats: {
    extracted: 0,
    saved: 0,
    errors: 0,
    total: 0
  }
};

// Elementos DOM
const elements = {
  // Status
  falcaoStatus: document.getElementById('falcao-status'),
  driveStatus: document.getElementById('drive-status'),

  // Drive
  btnConnectDrive: document.getElementById('btn-connect-drive'),
  btnDisconnectDrive: document.getElementById('btn-disconnect-drive'),

  // Config
  folderName: document.getElementById('folder-name'),
  fileFormat: document.getElementById('file-format'),
  delayTime: document.getElementById('delay-time'),
  includeMetadata: document.getElementById('include-metadata'),
  consolidateFile: document.getElementById('consolidate-file'),

  // Extraction
  pageInfo: document.getElementById('page-info'),
  resultsInfo: document.getElementById('results-info'),
  totalResults: document.getElementById('total-results'),
  currentPage: document.getElementById('current-page'),
  btnStart: document.getElementById('btn-start'),
  btnPause: document.getElementById('btn-pause'),
  btnStop: document.getElementById('btn-stop'),

  // Progress
  progressSection: document.getElementById('progress-section'),
  progressFill: document.getElementById('progress-fill'),
  progressText: document.getElementById('progress-text'),
  extractedCount: document.getElementById('extracted-count'),
  savedCount: document.getElementById('saved-count'),
  errorCount: document.getElementById('error-count'),
  currentItemText: document.getElementById('current-item-text'),

  // Log
  logContainer: document.getElementById('log-container'),
  btnClearLog: document.getElementById('btn-clear-log')
};

// Inicialização
document.addEventListener('DOMContentLoaded', init);

async function init() {
  log('Inicializando extensão...', 'info');

  // Carregar configurações salvas
  await loadSettings();

  // Verificar estado do Drive
  await checkDriveConnection();

  // Verificar se está na página do Falcão
  await checkFalcaoPage();

  // Configurar event listeners
  setupEventListeners();

  log('Extensão pronta.', 'success');
}

function setupEventListeners() {
  // Drive
  elements.btnConnectDrive.addEventListener('click', connectToDrive);
  elements.btnDisconnectDrive.addEventListener('click', disconnectFromDrive);

  // Config
  elements.folderName.addEventListener('change', saveSettings);
  elements.fileFormat.addEventListener('change', saveSettings);
  elements.delayTime.addEventListener('change', saveSettings);
  elements.includeMetadata.addEventListener('change', saveSettings);
  elements.consolidateFile.addEventListener('change', saveSettings);

  // Extraction
  elements.btnStart.addEventListener('click', startExtraction);
  elements.btnPause.addEventListener('click', togglePause);
  elements.btnStop.addEventListener('click', stopExtraction);

  // Log
  elements.btnClearLog.addEventListener('click', clearLog);

  // Escutar mensagens do content script
  chrome.runtime.onMessage.addListener(handleMessage);
}

// ==================== Google Drive ====================

async function connectToDrive() {
  log('Conectando ao Google Drive...', 'info');

  try {
    // Usar chrome.identity para autenticação OAuth2
    const token = await new Promise((resolve, reject) => {
      chrome.identity.getAuthToken({ interactive: true }, (token) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve(token);
        }
      });
    });

    state.accessToken = token;
    state.isConnectedToDrive = true;

    // Salvar token
    await chrome.storage.local.set({ driveToken: token });

    // Criar/verificar pasta no Drive
    await ensureDriveFolder();

    updateDriveStatus(true);
    log('Conectado ao Google Drive com sucesso!', 'success');
    updateStartButton();

  } catch (error) {
    log(`Erro ao conectar ao Drive: ${error.message}`, 'error');
    updateDriveStatus(false);
  }
}

async function disconnectFromDrive() {
  try {
    if (state.accessToken) {
      // Revogar token
      chrome.identity.removeCachedAuthToken({ token: state.accessToken }, () => {
        log('Desconectado do Google Drive.', 'info');
      });
    }

    state.accessToken = null;
    state.isConnectedToDrive = false;
    state.folderId = null;

    await chrome.storage.local.remove(['driveToken', 'driveFolderId']);

    updateDriveStatus(false);
    updateStartButton();

  } catch (error) {
    log(`Erro ao desconectar: ${error.message}`, 'error');
  }
}

async function checkDriveConnection() {
  try {
    const data = await chrome.storage.local.get(['driveToken', 'driveFolderId']);

    if (data.driveToken) {
      // Verificar se o token ainda é válido
      const response = await fetch('https://www.googleapis.com/drive/v3/about?fields=user', {
        headers: {
          'Authorization': `Bearer ${data.driveToken}`
        }
      });

      if (response.ok) {
        state.accessToken = data.driveToken;
        state.folderId = data.driveFolderId;
        state.isConnectedToDrive = true;
        updateDriveStatus(true);
        return;
      }
    }

    updateDriveStatus(false);

  } catch (error) {
    updateDriveStatus(false);
  }
}

async function ensureDriveFolder() {
  const folderName = elements.folderName.value || 'Acórdãos Falcão';

  try {
    // Verificar se a pasta já existe
    const searchResponse = await fetch(
      `https://www.googleapis.com/drive/v3/files?q=name='${encodeURIComponent(folderName)}' and mimeType='application/vnd.google-apps.folder' and trashed=false`,
      {
        headers: {
          'Authorization': `Bearer ${state.accessToken}`
        }
      }
    );

    const searchData = await searchResponse.json();

    if (searchData.files && searchData.files.length > 0) {
      state.folderId = searchData.files[0].id;
      log(`Pasta encontrada: ${folderName}`, 'info');
    } else {
      // Criar nova pasta
      const createResponse = await fetch('https://www.googleapis.com/drive/v3/files', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${state.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: folderName,
          mimeType: 'application/vnd.google-apps.folder'
        })
      });

      const createData = await createResponse.json();
      state.folderId = createData.id;
      log(`Pasta criada: ${folderName}`, 'success');
    }

    await chrome.storage.local.set({ driveFolderId: state.folderId });

  } catch (error) {
    log(`Erro ao criar pasta: ${error.message}`, 'error');
    throw error;
  }
}

async function uploadToDrive(fileName, content, mimeType = 'text/plain') {
  try {
    const metadata = {
      name: fileName,
      parents: [state.folderId]
    };

    const form = new FormData();
    form.append('metadata', new Blob([JSON.stringify(metadata)], { type: 'application/json' }));
    form.append('file', new Blob([content], { type: mimeType }));

    const response = await fetch(
      'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${state.accessToken}`
        },
        body: form
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.id;

  } catch (error) {
    log(`Erro ao fazer upload: ${error.message}`, 'error');
    throw error;
  }
}

function updateDriveStatus(connected) {
  if (connected) {
    elements.driveStatus.textContent = 'Conectado';
    elements.driveStatus.className = 'status-badge connected';
    elements.btnConnectDrive.classList.add('hidden');
    elements.btnDisconnectDrive.classList.remove('hidden');
  } else {
    elements.driveStatus.textContent = 'Desconectado';
    elements.driveStatus.className = 'status-badge disconnected';
    elements.btnConnectDrive.classList.remove('hidden');
    elements.btnDisconnectDrive.classList.add('hidden');
  }
}

// ==================== Falcão Page ====================

async function checkFalcaoPage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab && tab.url && tab.url.includes('jurisprudencia.jt.jus.br')) {
      state.isOnFalcaoPage = true;
      elements.falcaoStatus.textContent = 'Conectado';
      elements.falcaoStatus.className = 'status-badge connected';

      // Solicitar informações da página
      chrome.tabs.sendMessage(tab.id, { action: 'getPageInfo' }, (response) => {
        if (response) {
          updatePageInfo(response);
        }
      });

    } else {
      state.isOnFalcaoPage = false;
      elements.falcaoStatus.textContent = 'Não está na página';
      elements.falcaoStatus.className = 'status-badge warning';
    }

    updateStartButton();

  } catch (error) {
    log(`Erro ao verificar página: ${error.message}`, 'error');
  }
}

function updatePageInfo(info) {
  if (info.totalResults > 0) {
    elements.pageInfo.classList.add('hidden');
    elements.resultsInfo.classList.remove('hidden');
    elements.totalResults.textContent = info.totalResults;
    elements.currentPage.textContent = info.currentPage || 1;
    state.stats.total = info.totalResults;
  }
}

// ==================== Extraction ====================

async function startExtraction() {
  if (!state.isConnectedToDrive) {
    log('Conecte ao Google Drive primeiro!', 'warning');
    return;
  }

  if (!state.isOnFalcaoPage) {
    log('Acesse o Sistema Falcão primeiro!', 'warning');
    return;
  }

  log('Iniciando extração...', 'info');

  state.isExtracting = true;
  state.isPaused = false;
  state.stats = { extracted: 0, saved: 0, errors: 0, total: state.stats.total };

  // Atualizar UI
  elements.btnStart.classList.add('hidden');
  elements.btnPause.classList.remove('hidden');
  elements.btnStop.classList.remove('hidden');
  elements.progressSection.classList.remove('hidden');

  // Enviar comando para content script
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  const config = {
    action: 'startExtraction',
    settings: {
      delay: parseInt(elements.delayTime.value) || 2000,
      includeMetadata: elements.includeMetadata.checked,
      consolidate: elements.consolidateFile.checked,
      format: elements.fileFormat.value
    }
  };

  chrome.tabs.sendMessage(tab.id, config);
}

function togglePause() {
  state.isPaused = !state.isPaused;

  if (state.isPaused) {
    elements.btnPause.textContent = 'Continuar';
    log('Extração pausada.', 'warning');
  } else {
    elements.btnPause.textContent = 'Pausar';
    log('Extração retomada.', 'info');
  }

  // Enviar comando para content script
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    chrome.tabs.sendMessage(tab.id, { action: state.isPaused ? 'pause' : 'resume' });
  });
}

async function stopExtraction() {
  state.isExtracting = false;
  state.isPaused = false;

  // Atualizar UI
  elements.btnStart.classList.remove('hidden');
  elements.btnPause.classList.add('hidden');
  elements.btnStop.classList.add('hidden');
  elements.btnPause.textContent = 'Pausar';

  log('Extração interrompida.', 'warning');

  // Enviar comando para content script
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    chrome.tabs.sendMessage(tab.id, { action: 'stop' });
  });

  // Se consolidar está ativado, criar arquivo consolidado
  if (elements.consolidateFile.checked && state.stats.extracted > 0) {
    await createConsolidatedFile();
  }
}

async function createConsolidatedFile() {
  log('Criando arquivo consolidado...', 'info');

  try {
    // Solicitar dados consolidados do content script
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    chrome.tabs.sendMessage(tab.id, { action: 'getConsolidatedData' }, async (response) => {
      if (response && response.data) {
        const fileName = `Acordaos_Consolidado_${new Date().toISOString().slice(0, 10)}.txt`;
        await uploadToDrive(fileName, response.data, 'text/plain');
        log(`Arquivo consolidado salvo: ${fileName}`, 'success');
      }
    });

  } catch (error) {
    log(`Erro ao criar arquivo consolidado: ${error.message}`, 'error');
  }
}

function updateStartButton() {
  elements.btnStart.disabled = !state.isConnectedToDrive || !state.isOnFalcaoPage;
}

// ==================== Message Handling ====================

function handleMessage(message, sender, sendResponse) {
  switch (message.type) {
    case 'pageInfo':
      updatePageInfo(message.data);
      break;

    case 'extractionProgress':
      updateProgress(message.data);
      break;

    case 'acordaoExtracted':
      handleAcordaoExtracted(message.data);
      break;

    case 'extractionComplete':
      handleExtractionComplete(message.data);
      break;

    case 'error':
      state.stats.errors++;
      elements.errorCount.textContent = state.stats.errors;
      log(`Erro: ${message.data}`, 'error');
      break;

    case 'log':
      log(message.data.message, message.data.type || 'info');
      break;
  }

  sendResponse({ received: true });
  return true;
}

function updateProgress(data) {
  const percent = Math.round((data.current / data.total) * 100);

  elements.progressFill.style.width = `${percent}%`;
  elements.progressText.textContent = `${percent}%`;
  elements.currentItemText.textContent = data.currentItem || '-';
}

async function handleAcordaoExtracted(data) {
  state.stats.extracted++;
  elements.extractedCount.textContent = state.stats.extracted;

  log(`Extraído: ${data.numero || 'Acórdão ' + state.stats.extracted}`, 'success');

  // Fazer upload para o Drive
  try {
    const fileName = sanitizeFileName(data.numero || `acordao_${state.stats.extracted}`) +
                     '.' + elements.fileFormat.value;

    let content = '';

    if (elements.includeMetadata.checked) {
      content += `ACÓRDÃO: ${data.numero || 'N/A'}\n`;
      content += `RELATOR: ${data.relator || 'N/A'}\n`;
      content += `ÓRGÃO JULGADOR: ${data.orgaoJulgador || 'N/A'}\n`;
      content += `DATA: ${data.dataJulgamento || 'N/A'}\n`;
      content += `${'='.repeat(60)}\n\n`;
    }

    content += data.inteiroTeor || '';

    await uploadToDrive(fileName, content);

    state.stats.saved++;
    elements.savedCount.textContent = state.stats.saved;

  } catch (error) {
    state.stats.errors++;
    elements.errorCount.textContent = state.stats.errors;
    log(`Erro ao salvar: ${error.message}`, 'error');
  }
}

function handleExtractionComplete(data) {
  state.isExtracting = false;

  elements.btnStart.classList.remove('hidden');
  elements.btnPause.classList.add('hidden');
  elements.btnStop.classList.add('hidden');

  log(`Extração concluída! ${state.stats.saved} acórdãos salvos.`, 'success');

  // Criar arquivo consolidado se configurado
  if (elements.consolidateFile.checked) {
    createConsolidatedFile();
  }
}

// ==================== Settings ====================

async function loadSettings() {
  try {
    const data = await chrome.storage.local.get([
      'folderName',
      'fileFormat',
      'delayTime',
      'includeMetadata',
      'consolidateFile'
    ]);

    if (data.folderName) elements.folderName.value = data.folderName;
    if (data.fileFormat) elements.fileFormat.value = data.fileFormat;
    if (data.delayTime) elements.delayTime.value = data.delayTime;
    if (data.includeMetadata !== undefined) elements.includeMetadata.checked = data.includeMetadata;
    if (data.consolidateFile !== undefined) elements.consolidateFile.checked = data.consolidateFile;

  } catch (error) {
    log(`Erro ao carregar configurações: ${error.message}`, 'error');
  }
}

async function saveSettings() {
  try {
    await chrome.storage.local.set({
      folderName: elements.folderName.value,
      fileFormat: elements.fileFormat.value,
      delayTime: elements.delayTime.value,
      includeMetadata: elements.includeMetadata.checked,
      consolidateFile: elements.consolidateFile.checked
    });

  } catch (error) {
    log(`Erro ao salvar configurações: ${error.message}`, 'error');
  }
}

// ==================== Utilities ====================

function log(message, type = 'info') {
  const entry = document.createElement('p');
  entry.className = `log-entry ${type}`;

  const time = new Date().toLocaleTimeString('pt-BR');
  entry.textContent = `[${time}] ${message}`;

  elements.logContainer.appendChild(entry);
  elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
}

function clearLog() {
  elements.logContainer.innerHTML = '';
  log('Log limpo.', 'info');
}

function sanitizeFileName(name) {
  return name
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/\s+/g, '_')
    .substring(0, 100);
}
