import { CONFIG } from './config.js';

const STORAGE_KEY = 'atlas_urbano_logs';
const MAX_LOGS = 500;
const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };

// Get initial configured level (URL > CONFIG > INFO)
const urlParams = new URLSearchParams(window.location.search);
const urlLevel = urlParams.get('logLevel')?.toUpperCase();
let currentLogLevel = LEVELS[urlLevel] ?? LEVELS[CONFIG.LOG_LEVEL] ?? LEVELS.INFO;

// Session ID
const sessionId = crypto.randomUUID();

// In-memory buffer
let logBuffer = [];

// Load from local storage
try {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    logBuffer = JSON.parse(stored);
  }
} catch (e) {
  console.warn('Falha ao carregar logs do localStorage', e);
}

function persistLogs() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(logBuffer));
  } catch (e) {
    // QuotaExceededError or disabled
  }
}

function addLog(levelStr, module, message, data) {
  if (LEVELS[levelStr] < currentLogLevel) return;

  const entry = {
    timestamp: new Date().toISOString(),
    level: levelStr,
    sessionId,
    module,
    message,
    data
  };

  logBuffer.push(entry);
  if (logBuffer.length > MAX_LOGS) {
    logBuffer.shift();
  }
  
  persistLogs();

  const formattedMsg = `[${entry.timestamp}] [${levelStr}] [${module}] ${message}`;
  if (data !== undefined) {
    if (levelStr === 'DEBUG') console.debug(formattedMsg, data);
    else if (levelStr === 'INFO') console.info(formattedMsg, data);
    else if (levelStr === 'WARN') console.warn(formattedMsg, data);
    else if (levelStr === 'ERROR') console.error(formattedMsg, data);
  } else {
    if (levelStr === 'DEBUG') console.debug(formattedMsg);
    else if (levelStr === 'INFO') console.info(formattedMsg);
    else if (levelStr === 'WARN') console.warn(formattedMsg);
    else if (levelStr === 'ERROR') console.error(formattedMsg);
  }
}

// Global error handlers
window.addEventListener('error', (event) => {
  addLog('ERROR', 'global', 'Uncaught error', {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
    error: event.error ? { message: event.error.message, stack: event.error.stack } : null
  });
});

window.addEventListener('unhandledrejection', (event) => {
  addLog('ERROR', 'global', 'Unhandled Promise rejection', {
    reason: event.reason instanceof Error ? { message: event.reason.message, stack: event.reason.stack } : event.reason
  });
});

export const Logger = {
  create: (moduleName) => {
    return {
      debug: (msg, data) => addLog('DEBUG', moduleName, msg, data),
      info: (msg, data) => addLog('INFO', moduleName, msg, data),
      warn: (msg, data) => addLog('WARN', moduleName, msg, data),
      error: (msg, data) => addLog('ERROR', moduleName, msg, data),
    };
  },
  export: () => JSON.stringify(logBuffer, null, 2),
  download: () => {
    const blob = new Blob([JSON.stringify(logBuffer, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `atlas_urbano_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },
  clear: () => {
    logBuffer = [];
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    console.info('Logs cleared');
  }
};

window.__AtlasLogs = Logger;
