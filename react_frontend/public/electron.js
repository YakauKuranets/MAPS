const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');

// ═══ WebGPU/Vulkan acceleration ═══
app.commandLine.appendSwitch('enable-unsafe-webgpu');
app.commandLine.appendSwitch('enable-features', 'Vulkan,VulkanFromANGLE,DefaultANGLEVulkan');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('disable-frame-rate-limit');

// ═══ Hardened CSP ═══
const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com",
  "connect-src 'self' ws://localhost:* wss://*.yjs.dev https://api.mapbox.com",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
].join('; ');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    backgroundColor: '#020202',
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      nodeIntegration: false,          // ✅ SECURE: Node.js disabled in renderer
      contextIsolation: true,          // ✅ SECURE: Sandbox isolation
      sandbox: true,                   // ✅ SECURE: Chromium sandbox
      preload: path.join(__dirname, 'preload.js'),
      webgl: true,
      spellcheck: false,
      enableWebSQL: false,
    },
  });

  // ═══ Inject CSP headers ═══
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [CSP],
      },
    });
  });

  const startUrl = isDev
    ? 'http://localhost:3000'
    : `file://${path.join(__dirname, '../build/index.html')}`;

  mainWindow.loadURL(startUrl);

  if (isDev) mainWindow.webContents.openDevTools();
  mainWindow.on('closed', () => { mainWindow = null; });

  // ═══ Block new window creation (anti-phishing) ═══
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
}

// ═══ IPC Handlers ═══
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.on('set-always-on-top', (_e, flag) => mainWindow?.setAlwaysOnTop(flag));
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
