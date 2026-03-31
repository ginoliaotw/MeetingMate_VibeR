/**
 * MeetingMate — Electron main process
 *
 * 啟動流程：
 * 1. 啟動 Python FastAPI 後端 (backend/main.py)
 * 2. 等待後端 HTTP ready
 * 3. 建立 BrowserWindow 顯示前端 UI
 * 4. 關閉視窗時終止後端 process
 */

const { app, BrowserWindow, dialog, shell, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const PORT = 18765; // 避免與系統服務衝突
let mainWindow = null;
let backendProcess = null;
let backendReady = false;

// ─── 找 Python 執行檔 ───────────────────────────────────────
function findPython() {
  // 優先使用打包進 .app 的 Python，其次使用系統 Python
  const candidates = [
    path.join(process.resourcesPath, 'backend_bin', 'meetingmate-server'), // PyInstaller 打包
    path.join(__dirname, '..', '.venv', 'bin', 'python3'),
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return 'python3';
}

// ─── 啟動 FastAPI 後端 ──────────────────────────────────────
function startBackend() {
  const python = findPython();
  const isPyInstaller = python.endsWith('meetingmate-server');

  let args, cwd;
  if (isPyInstaller) {
    args = [`--port=${PORT}`];
    cwd = path.dirname(python);
  } else {
    const backendDir = path.join(__dirname, '..', 'backend');
    args = ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', `--port=${PORT}`];
    cwd = backendDir;
  }

  console.log(`[Backend] Starting: ${python} ${args.join(' ')} in ${cwd}`);

  backendProcess = spawn(python, args, {
    cwd,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      MEETINGMATE_PORT: String(PORT),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString().trim()));
  backendProcess.stderr.on('data', (d) => console.error('[Backend ERR]', d.toString().trim()));
  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Exited with code ${code}`);
    backendReady = false;
  });
}

// ─── 輪詢後端直到 ready ─────────────────────────────────────
function waitForBackend(retries = 60) {
  return new Promise((resolve, reject) => {
    const check = (n) => {
      if (n <= 0) return reject(new Error('Backend did not start in time'));
      http.get(`http://127.0.0.1:${PORT}/api/settings`, (res) => {
        if (res.statusCode < 500) {
          backendReady = true;
          resolve();
        } else {
          setTimeout(() => check(n - 1), 1000);
        }
      }).on('error', () => setTimeout(() => check(n - 1), 1000));
    };
    check(retries);
  });
}

// ─── 建立主視窗 ─────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    title: 'MeetingMate',
    titleBarStyle: 'hiddenInset', // macOS 原生標題列樣式
    backgroundColor: '#f5f5f5',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`);

  // 外部連結用系統瀏覽器開啟
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ─── macOS 選單 ─────────────────────────────────────────────
function buildMenu() {
  const template = [
    {
      label: 'MeetingMate',
      submenu: [
        { role: 'about', label: '關於 MeetingMate' },
        { type: 'separator' },
        { role: 'services', label: '服務' },
        { type: 'separator' },
        { role: 'hide', label: '隱藏 MeetingMate' },
        { role: 'hideOthers', label: '隱藏其他' },
        { role: 'unhide', label: '全部顯示' },
        { type: 'separator' },
        { role: 'quit', label: '結束 MeetingMate' },
      ],
    },
    {
      label: '編輯',
      submenu: [
        { role: 'undo', label: '復原' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪下' },
        { role: 'copy', label: '拷貝' },
        { role: 'paste', label: '貼上' },
        { role: 'selectAll', label: '全選' },
      ],
    },
    {
      label: '視窗',
      submenu: [
        { role: 'minimize', label: '縮小' },
        { role: 'zoom', label: '縮放' },
        { type: 'separator' },
        { role: 'front', label: '移至最前' },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ─── App 生命週期 ────────────────────────────────────────────
app.whenReady().then(async () => {
  buildMenu();
  startBackend();

  // 顯示載入中視窗
  mainWindow = new BrowserWindow({
    width: 480,
    height: 300,
    resizable: false,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#1e1e2e',
    webPreferences: { nodeIntegration: false },
  });
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));

  try {
    await waitForBackend();
    mainWindow.close();
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      'MeetingMate 啟動失敗',
      `無法啟動後端服務：\n${err.message}\n\n請確認 Python 3.10+ 已安裝，並執行：\n  pip install -r backend/requirements.txt`
    );
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (mainWindow === null && backendReady) createWindow();
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
  }
});
