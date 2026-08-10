// 花火邮箱助手环境配置
// 此文件被前端index.html引用，用于配置API地址

// API地址配置（仅在未设置时提供默认值）
if (!window.API_URL) window.API_URL = '/api';
// WebSocket地址配置（仅在未设置时提供默认值）
if (!window.WS_URL) window.WS_URL = '/ws';

console.log('env-config.js已加载，API_URL:', window.API_URL, 'WS_URL:', window.WS_URL);
