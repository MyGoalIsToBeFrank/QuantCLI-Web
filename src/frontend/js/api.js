/**
 * api.js
 * 封装所有后端 API 调用，统一处理错误
 */

const BASE_URL = CONFIG.API_BASE;

/**
 * 通用 fetch 封装
 * @param {string} url 请求地址
 * @param {object} options fetch 选项
 * @returns {Promise<any>} 返回后端 JSON 数据
 */
async function request(url, options = {}) {
  const response = await fetch(url, options);

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message = data && data.message ? data.message : `HTTP ${response.status}`;
    throw new Error(message);
  }

  return data;
}

/**
 * 获取股票池
 */
function getStocks() {
  return request(`${BASE_URL}/api/stocks`);
}

/**
 * 获取单只股票 K 线数据
 */
function getStockData(symbol) {
  return request(`${BASE_URL}/api/stock_data?symbol=${encodeURIComponent(symbol)}`);
}

/**
 * 更新单只股票数据
 */
function updateStock(symbol) {
  return request(`${BASE_URL}/api/update_stock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol })
  });
}

/**
 * 获取 Pipeline 列表
 */
function getPipelines() {
  return request(`${BASE_URL}/api/pipelines`);
}

/**
 * 获取 Strategy 列表
 */
function getStrategies() {
  return request(`${BASE_URL}/api/strategies`);
}

/**
 * 季度策略分析
 * @param {object} options {symbol, start, end, save, max_drawdown, pipelines, strategies}
 */
function analyzeStock(options) {
  return request(`${BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options)
  });
}

/**
 * 获取最佳组合
 */
function getBestCombo(symbol) {
  return request(`${BASE_URL}/api/best_combo?symbol=${encodeURIComponent(symbol)}`);
}

/**
 * 运行回测
 * @param {object} payload {symbol, pipeline, strategy, start, end, stop_loss, capital, fee, lot}
 */
function runBacktest(payload = {}) {
  return request(`${BASE_URL}/api/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/**
 * 单只股票今日决策
 * @param {object} options {symbol, open, capital, fee, lot}
 */
function decideStock(options) {
  const payload = { symbol: options.symbol };
  if (options.open !== undefined && options.open !== '') {
    payload.open = parseFloat(options.open);
  }
  if (options.capital !== undefined) payload.capital = parseFloat(options.capital);
  if (options.fee !== undefined) payload.fee = parseFloat(options.fee);
  if (options.lot !== undefined) payload.lot = parseInt(options.lot, 10);
  return request(`${BASE_URL}/api/decide_stock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/**
 * 批量综合报告
 * @param {object} options {symbols, start, end, max_drawdown, save, capital, fee, lot}
 */
function runBatchReport(options) {
  return request(`${BASE_URL}/api/batch_report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options)
  });
}

/**
 * 获取所有股票基本面分析记录
 */
function getFundamentalRecords() {
  return request(`${BASE_URL}/api/fundamental_records`);
}

/**
 * 获取某股票最新基本面报告内容
 */
function getFundamentalReport(symbol) {
  return request(`${BASE_URL}/api/fundamental_report?symbol=${encodeURIComponent(symbol)}`);
}

/* ============================================================
 * 组合决策（portfolio）
 * ========================================================== */

/** 获取组合账户状态 */
function getPortfolioState() {
  return request(`${BASE_URL}/api/portfolio_state`);
}

/** 整体更新组合状态（现金/持仓/lot_size） */
function putPortfolioState(payload) {
  return request(`${BASE_URL}/api/portfolio_state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/** 新增/更新单只持仓 */
function setPortfolioPosition(payload) {
  return request(`${BASE_URL}/api/portfolio_position`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/** 移除单只持仓 */
function deletePortfolioPosition(symbol) {
  return request(`${BASE_URL}/api/portfolio_position`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol })
  });
}

/** 获取风险配置 */
function getPortfolioRiskProfile() {
  return request(`${BASE_URL}/api/portfolio_risk_profile`);
}

/** 更新风险配置 */
function putPortfolioRiskProfile(payload) {
  return request(`${BASE_URL}/api/portfolio_risk_profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

/** 组合级今日决策 */
function portfolioDecide(payload) {
  return request(`${BASE_URL}/api/portfolio_decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}
