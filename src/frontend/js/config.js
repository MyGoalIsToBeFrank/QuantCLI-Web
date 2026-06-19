/**
 * config.js
 * 前端默认配置：后端地址、刷新间隔、图表主题色等
 */

const CONFIG = {
  // 后端 API 基地址
  API_BASE: 'http://127.0.0.1:5000',

  // 自动刷新间隔（毫秒），当前未启用轮询，仅作预留
  REFRESH_INTERVAL: 30000,

  // K 线颜色：红涨绿跌
  COLORS: {
    up: '#ff4d4f',            // 涨（红色）
    down: '#00b578',          // 跌（绿色）
    ma5: '#ffd666',           // MA5
    ma20: '#69b1ff',          // MA20
    ma60: '#b37feb',          // MA60
    volumeUp: 'rgba(255, 77, 79, 0.6)',
    volumeDown: 'rgba(0, 181, 120, 0.6)'
  }
};
