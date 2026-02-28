/**
 * Preload script — exposes safe IPC bridge to renderer.
 * Node.js is NOT accessible in renderer (contextIsolation: true).
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getPlatform: () => process.platform,
  onDeepLink: (callback) => ipcRenderer.on('deep-link', (_e, url) => callback(url)),
  sendTelemetry: (data) => ipcRenderer.send('telemetry', data),
  setAlwaysOnTop: (flag) => ipcRenderer.send('set-always-on-top', flag),
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
});
