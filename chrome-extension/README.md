# Extensão Chrome - Extrator de Acórdãos do Sistema Falcão

Esta extensão do Google Chrome automatiza a extração do inteiro teor dos acórdãos do Sistema Falcão (jurisprudência trabalhista) e salva diretamente no seu Google Drive.

## Funcionalidades

- Extrai automaticamente o inteiro teor dos acórdãos listados na busca
- Salva cada acórdão como arquivo individual no Google Drive
- Cria arquivo consolidado com todos os acórdãos
- Inclui metadados (número do processo, relator, data, etc.)
- Indicador visual de progresso na página
- Suporte a pausar/continuar/parar extração
- Navega automaticamente entre páginas de resultados

## Pré-requisitos

1. Google Chrome (versão 88 ou superior)
2. Conta Google para acesso ao Drive

## Instalação

### Passo 1: Configurar Google Cloud Console

Para a extensão se conectar ao Google Drive, você precisa criar credenciais OAuth:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)

2. Crie um novo projeto ou selecione um existente

3. Ative a **Google Drive API**:
   - Menu lateral → "APIs e Serviços" → "Biblioteca"
   - Pesquise "Google Drive API"
   - Clique em "Ativar"

4. Configure a tela de consentimento OAuth:
   - Menu lateral → "APIs e Serviços" → "Tela de consentimento OAuth"
   - Escolha "Externo"
   - Preencha os campos obrigatórios (nome do app, email de suporte)
   - Em "Escopos", adicione: `https://www.googleapis.com/auth/drive.file`
   - Adicione seu email como usuário de teste

5. Crie as credenciais:
   - Menu lateral → "APIs e Serviços" → "Credenciais"
   - Clique em "Criar credenciais" → "ID do cliente OAuth"
   - Tipo: **Extensão do Chrome**
   - Nome: "Extrator de Acórdãos"
   - ID do item: (deixe em branco por enquanto, ou use o ID após publicar)

6. Copie o **Client ID** gerado (algo como `123456789.apps.googleusercontent.com`)

### Passo 2: Configurar a Extensão

1. Abra o arquivo `manifest.json` nesta pasta

2. Substitua `SEU_CLIENT_ID_AQUI.apps.googleusercontent.com` pelo Client ID que você copiou:
   ```json
   "oauth2": {
     "client_id": "123456789.apps.googleusercontent.com",
     "scopes": [
       "https://www.googleapis.com/auth/drive.file"
     ]
   }
   ```

### Passo 3: Gerar os Ícones

1. Abra o arquivo `icons/generate_icons.html` no navegador

2. Clique em cada botão para baixar os ícones:
   - `icon16.png`
   - `icon32.png`
   - `icon48.png`
   - `icon128.png`

3. Salve os arquivos baixados na pasta `icons/`

### Passo 4: Instalar a Extensão no Chrome

1. Abra o Chrome e acesse `chrome://extensions/`

2. Ative o **"Modo do desenvolvedor"** (canto superior direito)

3. Clique em **"Carregar sem compactação"**

4. Selecione a pasta `chrome-extension` deste projeto

5. A extensão aparecerá na lista e o ícone será adicionado à barra de ferramentas

### Passo 5: Atualizar Client ID no Google Cloud (se necessário)

Após carregar a extensão, você verá o **ID da extensão** na página `chrome://extensions/`.

Se você deixou o campo "ID do item" em branco no passo 1.5, volte ao Google Cloud Console e atualize:
1. Vá em "Credenciais"
2. Clique no seu OAuth Client ID
3. Adicione o ID da extensão

## Como Usar

### 1. Fazer Login no Sistema Falcão

1. Acesse: https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa
2. Faça login com sua conta gov.br (opcional, mas recomendado para mais resultados)

### 2. Realizar a Busca

1. Deixe o campo de pesquisa em branco ou digite termos específicos
2. Aplique os filtros desejados:
   - **Tribunal:** TRT21
   - **Magistrada/Magistrado:** Bento Herculano Duarte Neto
   - **Período:** 01/01/2024 a 04/07/2025
3. Clique em buscar

### 3. Conectar ao Google Drive

1. Clique no ícone da extensão na barra de ferramentas
2. Clique em **"Conectar ao Google Drive"**
3. Autorize o acesso quando solicitado
4. Uma pasta "Acórdãos Falcão" será criada automaticamente no seu Drive

### 4. Configurar Extração

No popup da extensão, você pode configurar:

| Opção | Descrição |
|-------|-----------|
| Nome da pasta | Pasta no Drive onde salvar os arquivos |
| Formato do arquivo | TXT, DOCX ou PDF |
| Delay entre extrações | Tempo de espera entre cada acórdão (em ms) |
| Incluir metadados | Adiciona número, relator, data no início |
| Criar arquivo consolidado | Gera um arquivo único com todos os acórdãos |

### 5. Iniciar Extração

1. Com a busca feita e o Drive conectado, clique em **"Iniciar Extração"**
2. A extensão irá:
   - Percorrer cada resultado da busca
   - Extrair o inteiro teor de cada acórdão
   - Fazer upload para o Google Drive
   - Avançar para a próxima página automaticamente

3. Você pode:
   - **Pausar:** Pausa a extração (pode continuar depois)
   - **Parar:** Encerra a extração e salva o que foi coletado

### 6. Acompanhar Progresso

- A barra de progresso mostra o andamento
- O contador mostra: Extraídos / Salvos / Erros
- O log mostra mensagens detalhadas
- Um indicador aparece na página do Falcão

## Arquivos Gerados no Drive

### Arquivos Individuais
```
Acórdãos Falcão/
├── 0001234-56.2024.5.21.0001.txt
├── 0001235-56.2024.5.21.0002.txt
├── 0001236-56.2024.5.21.0003.txt
└── ...
```

### Arquivo Consolidado
```
Acordaos_Consolidado_2024-12-10.txt
```

## Estrutura dos Arquivos

Cada arquivo contém:

```
NÚMERO DO PROCESSO: 0001234-56.2024.5.21.0001
RELATOR: Bento Herculano Duarte Neto
ÓRGÃO JULGADOR: 1ª Turma
DATA DE JULGAMENTO: 15/03/2024
URL: https://jurisprudencia.jt.jus.br/...
============================================================

EMENTA:
----------------------------------------
[Texto da ementa]

INTEIRO TEOR:
----------------------------------------
[Texto completo do acórdão]
```

## Solução de Problemas

### Erro "Não autenticado no Google Drive"
- Desconecte e reconecte ao Drive
- Verifique se as credenciais OAuth estão corretas

### "Nenhum resultado encontrado na página"
- Certifique-se de que fez uma busca antes de iniciar
- Verifique se há resultados na página

### Extração muito lenta
- Aumente o delay se estiver tendo erros
- Reduza o delay se quiser mais velocidade (pode causar bloqueios)

### Site bloqueia requisições
- Use intervalos maiores entre extrações (3000-5000ms)
- Faça login no sistema para ter mais acesso

### Ícones não aparecem
- Gere os ícones usando o arquivo `icons/generate_icons.html`
- Certifique-se de que estão na pasta `icons/`

## Limitações

- Requer que a página esteja aberta e ativa
- Usuários sem login podem ver até 200 documentos
- A estrutura do site pode mudar e quebrar a extração

## Estrutura dos Arquivos da Extensão

```
chrome-extension/
├── manifest.json       # Configuração da extensão
├── popup.html          # Interface do popup
├── popup.css           # Estilos do popup
├── popup.js            # Lógica do popup
├── content.js          # Script injetado na página
├── content.css         # Estilos injetados
├── background.js       # Service worker
├── icons/
│   ├── icon.svg        # Ícone fonte (SVG)
│   ├── icon16.png      # 16x16 pixels
│   ├── icon32.png      # 32x32 pixels
│   ├── icon48.png      # 48x48 pixels
│   ├── icon128.png     # 128x128 pixels
│   └── generate_icons.html  # Gerador de ícones
└── README.md           # Esta documentação
```

## Desenvolvimento

Para modificar a extensão:

1. Faça alterações nos arquivos
2. Vá em `chrome://extensions/`
3. Clique no botão de atualizar da extensão
4. Recarregue a página do Falcão

## Licença

Uso educacional e de pesquisa. Respeite os termos de uso do Sistema Falcão.
