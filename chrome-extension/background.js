/**
 * Background Service Worker - Extrator de Acórdãos do Sistema Falcão
 */

// Configurações
const CONFIG = {
  FALCAO_URL_PATTERN: '*://jurisprudencia.jt.jus.br/*',
  DRIVE_SCOPES: ['https://www.googleapis.com/auth/drive.file']
};

// Estado global
let extractionState = {
  isActive: false,
  tabId: null,
  stats: {
    extracted: 0,
    saved: 0,
    errors: 0
  }
};

// Instalação da extensão
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[Background] Extensão instalada:', details.reason);

  if (details.reason === 'install') {
    // Configurações padrão
    chrome.storage.local.set({
      folderName: 'Acórdãos Falcão',
      fileFormat: 'txt',
      delayTime: 2000,
      includeMetadata: true,
      consolidateFile: true
    });

    // Abrir página de boas-vindas
    chrome.tabs.create({
      url: 'https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa'
    });
  }
});

// Escutar mensagens
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[Background] Mensagem recebida:', message);

  handleMessage(message, sender)
    .then(response => sendResponse(response))
    .catch(error => sendResponse({ error: error.message }));

  return true; // Mantém o canal aberto para resposta assíncrona
});

async function handleMessage(message, sender) {
  switch (message.action) {
    case 'checkAuth':
      return await checkGoogleAuth();

    case 'getAuthToken':
      return await getAuthToken(message.interactive);

    case 'uploadToDrive':
      return await uploadFileToDrive(message.data);

    case 'createDriveFolder':
      return await createDriveFolder(message.folderName);

    case 'updateStats':
      updateExtractionStats(message.stats);
      return { success: true };

    case 'openOptionsPage':
      chrome.runtime.openOptionsPage();
      return { success: true };

    default:
      return { error: 'Ação não reconhecida' };
  }
}

// ==================== Google Auth ====================

async function checkGoogleAuth() {
  try {
    const token = await new Promise((resolve, reject) => {
      chrome.identity.getAuthToken({ interactive: false }, (token) => {
        if (chrome.runtime.lastError) {
          resolve(null);
        } else {
          resolve(token);
        }
      });
    });

    if (token) {
      // Verificar se o token é válido
      const response = await fetch('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=' + token);
      if (response.ok) {
        return { authenticated: true, token };
      }
    }

    return { authenticated: false };

  } catch (error) {
    console.error('[Background] Erro ao verificar auth:', error);
    return { authenticated: false, error: error.message };
  }
}

async function getAuthToken(interactive = true) {
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (token) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve({ token });
      }
    });
  });
}

// ==================== Google Drive ====================

async function uploadFileToDrive(data) {
  const { fileName, content, folderId, mimeType = 'text/plain' } = data;

  try {
    const { token } = await getAuthToken(false);

    if (!token) {
      throw new Error('Não autenticado no Google Drive');
    }

    const metadata = {
      name: fileName,
      mimeType: mimeType
    };

    if (folderId) {
      metadata.parents = [folderId];
    }

    // Upload multipart
    const boundary = 'extrator_falcao_boundary';

    const body = `--${boundary}
Content-Type: application/json; charset=UTF-8

${JSON.stringify(metadata)}
--${boundary}
Content-Type: ${mimeType}

${content}
--${boundary}--`;

    const response = await fetch(
      'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': `multipart/related; boundary=${boundary}`
        },
        body: body
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error?.message || 'Erro no upload');
    }

    const result = await response.json();
    return { success: true, fileId: result.id, fileName: result.name };

  } catch (error) {
    console.error('[Background] Erro no upload:', error);
    return { success: false, error: error.message };
  }
}

async function createDriveFolder(folderName) {
  try {
    const { token } = await getAuthToken(false);

    if (!token) {
      throw new Error('Não autenticado no Google Drive');
    }

    // Verificar se a pasta já existe
    const searchResponse = await fetch(
      `https://www.googleapis.com/drive/v3/files?q=name='${encodeURIComponent(folderName)}' and mimeType='application/vnd.google-apps.folder' and trashed=false`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    const searchData = await searchResponse.json();

    if (searchData.files && searchData.files.length > 0) {
      return { success: true, folderId: searchData.files[0].id, existed: true };
    }

    // Criar nova pasta
    const createResponse = await fetch(
      'https://www.googleapis.com/drive/v3/files',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: folderName,
          mimeType: 'application/vnd.google-apps.folder'
        })
      }
    );

    if (!createResponse.ok) {
      throw new Error('Erro ao criar pasta');
    }

    const createData = await createResponse.json();
    return { success: true, folderId: createData.id, existed: false };

  } catch (error) {
    console.error('[Background] Erro ao criar pasta:', error);
    return { success: false, error: error.message };
  }
}

// ==================== Gerenciamento de Estado ====================

function updateExtractionStats(stats) {
  extractionState.stats = { ...extractionState.stats, ...stats };

  // Atualizar badge
  const total = stats.extracted || 0;
  chrome.action.setBadgeText({ text: total > 0 ? String(total) : '' });
  chrome.action.setBadgeBackgroundColor({ color: '#1a73e8' });
}

// ==================== Context Menu ====================

chrome.runtime.onInstalled.addListener(() => {
  // Criar menu de contexto para links
  chrome.contextMenus.create({
    id: 'extrair-acordao',
    title: 'Extrair este acórdão',
    contexts: ['link'],
    documentUrlPatterns: ['*://jurisprudencia.jt.jus.br/*']
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'extrair-acordao') {
    // Enviar comando para extrair acórdão específico
    chrome.tabs.sendMessage(tab.id, {
      action: 'extractSingle',
      url: info.linkUrl
    });
  }
});

// ==================== Atalhos de Teclado ====================

chrome.commands.onCommand.addListener((command) => {
  if (command === 'start-extraction') {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (tab.url.includes('jurisprudencia.jt.jus.br')) {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleExtraction' });
      }
    });
  }
});

// ==================== Notificações ====================

function showNotification(title, message, type = 'info') {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title: title,
    message: message,
    priority: type === 'error' ? 2 : 1
  });
}

// Escutar quando a extração termina para mostrar notificação
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'extractionComplete') {
    showNotification(
      'Extração Concluída',
      `${message.data.total} acórdãos extraídos com sucesso!`,
      'success'
    );
  }

  if (message.type === 'error') {
    showNotification(
      'Erro na Extração',
      message.data,
      'error'
    );
  }
});

console.log('[Background] Service worker iniciado');
