// Exposes a small, explicit API to the renderer (the normal Flask-served web pages) for the one
// thing they need from the main process: triggering/hearing about update checks. Kept deliberately
// tiny — contextIsolation stays on, nodeIntegration stays off; the page never gets direct Node/
// Electron access, only these two specific calls.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("chronologyBuilder", {
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  onUpdateStatus: (callback) => ipcRenderer.on("update-status", (_event, status) => callback(status)),
});
