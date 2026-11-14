"use strict";
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("hearth", {
  isDesktop: true,
  chooseDataDir: () => ipcRenderer.invoke("hearth:choose-data-dir"),
  openDataDir: () => ipcRenderer.invoke("hearth:open-data-dir"),
});
