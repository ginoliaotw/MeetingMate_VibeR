/**
 * Electron preload — contextIsolation bridge
 * 目前前端不需要 Node API，保留空 bridge 以便未來擴充。
 */
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('meetingMate', {
  platform: process.platform,
  version: process.env.npm_package_version || '1.0.0',
});
