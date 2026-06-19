/**
 * app.js
 * 页面主逻辑：多股票、多视图、策略分析
 */

// 全局状态
const state = {
  portfolio: {},
  config: {},
  stocks: [],
  currentSymbol: '002156.SZ',
  currentView: 'dashboard',
  stockData: [],
  backtest: {
    records: [],
    currentIndex: 0,
    isPlaying: false,
    timer: null,
    mode: 'close_only'
  }
};

/**
 * 日志
 * @param {string} msg 日志内容
 * @param {string} boxId 日志容器 id，默认 'log-box'
 */
function log(msg, boxId = 'log-box') {
  const box = document.getElementById(boxId);
  if (!box) return;
  const time = new Date().toLocaleTimeString('zh-CN');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `<span class="log-time">[${time}]</span>${escapeHtml(msg)}`;
  box.appendChild(entry);
  box.scrollTop = box.scrollHeight;
}

function setLoading(show, text = '处理中...') {
  const overlay = document.getElementById('loading-overlay');
  if (!overlay) return;
  overlay.querySelector('.loading-text').textContent = text;
  overlay.classList.toggle('hidden', !show);
}

function formatMoney(num) {
  if (num === undefined || num === null) return '--';
  return Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(num) {
  if (num === undefined || num === null) return '--';
  const sign = num >= 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(2)}%`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderHtmlTable(headers, rows) {
  if (!rows || rows.length === 0) return '<p>无数据</p>';
  const ths = headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');
  const trs = rows.map(row => {
    const tds = row.map(cell => `<td>${escapeHtml(String(cell ?? '--'))}</td>`).join('');
    return `<tr>${tds}</tr>`;
  }).join('');
  return `<table class="data-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
}

/**
 * 初始化股票选择器
 */
async function initStockSelector() {
  try {
    const res = await getStocks();
    state.stocks = res.stocks || [];

    const selects = [document.getElementById('stock-select'), document.getElementById('analysis-stock')];
    selects.forEach(sel => {
      if (!sel) return;
      sel.innerHTML = '';
      state.stocks.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.symbol;
        opt.textContent = `${s.symbol} ${s.name}`;
        sel.appendChild(opt);
      });
      sel.value = state.currentSymbol;
    });
  } catch (e) {
    log(`加载股票池失败：${e.message}`);
  }
}

async function initPipelineStrategySelectors() {
  try {
    const [pRes, sRes] = await Promise.all([getPipelines(), getStrategies()]);
    state.pipelines = pRes.pipelines || [];
    state.strategies = sRes.strategies || [];

    const pSelect = document.getElementById('bt-pipeline');
    const sSelect = document.getElementById('bt-strategy');
    if (pSelect) {
      pSelect.innerHTML = '';
      state.pipelines.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.name;
        opt.textContent = p.name;
        pSelect.appendChild(opt);
      });
    }
    if (sSelect) {
      sSelect.innerHTML = '';
      state.strategies.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.name;
        opt.textContent = s.name;
        sSelect.appendChild(opt);
      });
    }
  } catch (e) {
    log(`加载 Pipeline/Strategy 失败：${e.message}`);
  }
}

/**
 * 切换视图
 */
function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${viewName}`).classList.add('active');
  document.querySelectorAll('.nav-tab').forEach(el => el.classList.toggle('active', el.dataset.view === viewName));

  if (viewName === 'analysis') {
    loadBestComboForAnalysis();
  } else if (viewName === 'fundamental') {
    loadFundamentalRecords();
  } else if (viewName === 'portfolio') {
    loadPortfolioView();
  }
}

/**
 * 加载并渲染单只股票 K 线
 */
async function loadStockChart(symbol) {
  try {
    const res = await getStockData(symbol);
    state.stockData = res.data || [];
    document.getElementById('chart-title').textContent = `${symbol} K 线图`;
    renderStockChart('stock-chart', state.stockData);
  } catch (e) {
    log(`加载 ${symbol} 数据失败：${e.message}`);
  }
}

/**
 * 加载并显示仪表盘当前股票最佳组合
 */
async function loadDashboardBestCombo() {
  const box = document.getElementById('dashboard-best-combo');
  if (!box) return;
  try {
    const res = await getBestCombo(state.currentSymbol);
    if (res.combo) {
      const c = res.combo;
      const m = c.metrics || {};
      const pipeline = c.pipeline_name || c.pipeline || 'N/A';
      const strategy = c.strategy_id || c.strategy || 'N/A';
      const tr = c.time_range || {};
      box.innerHTML = `<strong>${pipeline} + ${strategy}</strong><br>` +
        `配置: ${c.pipeline_config_id || 'N/A'}<br>` +
        `区间: ${tr.start || 'N/A'} ~ ${tr.end || 'N/A'}<br>` +
        `收益: ${m.total_return_pct?.toFixed(2) ?? '--'}%<br>` +
        `回撤: ${m.max_drawdown_pct?.toFixed(2) ?? '--'}%<br>` +
        `夏普: ${m.sharpe?.toFixed(3) ?? '--'}<br>` +
        `评估: ${c.last_evaluated?.slice(0, 10) || 'N/A'}`;
      // 同步回测下拉框
      const pSel = document.getElementById('bt-pipeline');
      const sSel = document.getElementById('bt-strategy');
      if (pSel) pSel.value = pipeline;
      if (sSel) sSel.value = strategy;
    } else {
      box.textContent = '暂无最佳组合，请到策略分析页运行分析并保存。';
    }
  } catch (e) {
    box.textContent = `加载失败：${e.message}`;
  }
}

/**
 * 渲染策略输出
 */
function renderStrategyOutput(data) {
  const box = document.getElementById('strategy-output');
  if (!box) return;
  const lines = [];
  if (data.date) lines.push(`决策日期：${data.date}`);
  const price = data.open !== undefined ? data.open : data.price;
  if (price !== undefined) lines.push(`开盘价：${Number(price).toFixed(2)}`);
  if (data.gap_pct !== undefined) lines.push(`开盘跳空：${data.gap_pct.toFixed(2)}%`);
  if (data.prediction) {
    const p = data.prediction;
    if (p.prob_bull !== undefined) lines.push(`上涨概率：${(p.prob_bull * 100).toFixed(2)}%`);
    if (p.rsi !== undefined) lines.push(`RSI：${p.rsi.toFixed(2)}`);
    if (p.signal) lines.push(`信号：${p.signal}`);
  }
  if (data.decision) {
    lines.push(`操作：${data.decision.note || ''}`);
    lines.push(`目标仓位：${(data.decision.target_position * 100).toFixed(1)}%`);
    if (data.decision.trade_shares !== 0) {
      lines.push(`${data.decision.action === 'buy' ? '买入' : '卖出'} ${Math.abs(data.decision.trade_shares)} 股`);
    }
  }
  box.textContent = lines.join('\n');
}

/**
 * 渲染回测输出
 */
function renderBacktestOutput(res) {
  const box = document.getElementById('backtest-output');
  if (!box) return;
  const m = res.metrics || res.close_only || {};
  const mode = res.mode || (res.metrics ? 'combo' : 'close_only');
  const lines = [
    `模式：${mode}`,
    `区间：${m.start_date || '--'} ~ ${m.end_date || '--'}`,
    `最终资产：${formatMoney(m.final_value)} 元`,
    `总收益率：${m.total_return_pct?.toFixed(2) || '--'}%`,
    `最大回撤：${m.max_drawdown_pct?.toFixed(2) || '--'}%`,
    `交易次数：${m.trade_count || '--'}`,
    `手续费：${formatMoney(m.total_fees)}`,
    `胜率：${m.win_rate?.toFixed(2) || '--'}%`,
    `夏普：${m.sharpe?.toFixed(3) || '--'}`
  ];
  box.innerHTML = lines.join('<br>');
}

/**
 * 绑定事件
 */
function bindEvents() {
  // 视图切换
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });

  // 股票选择
  const stockSelect = document.getElementById('stock-select');
  if (stockSelect) {
    stockSelect.addEventListener('change', async () => {
      state.currentSymbol = stockSelect.value;
      await loadStockChart(state.currentSymbol);
      await loadDashboardBestCombo();
    });
  }

  // 更新数据
  document.getElementById('btn-update')?.addEventListener('click', async () => {
    setLoading(true, '正在更新数据...');
    try {
      const res = await updateStock(state.currentSymbol);
      log(res.message);
      await loadStockChart(state.currentSymbol);
    } catch (e) {
      log(`更新失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  // 运行决策
  document.getElementById('btn-predict')?.addEventListener('click', async () => {
    setLoading(true, '正在生成决策...');
    try {
      const openInput = document.getElementById('today-open').value;
      const res = await decideStock({
        symbol: state.currentSymbol,
        open: openInput,
        capital: document.getElementById('dp-capital').value,
        fee: document.getElementById('dp-fee').value,
        lot: document.getElementById('dp-lot').value
      });
      renderStrategyOutput(res);
      log(`决策：${res.decision?.note || ''}`);
    } catch (e) {
      log(`决策失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  // 运行组合回测
  document.getElementById('btn-backtest')?.addEventListener('click', async () => {
    setLoading(true, '正在运行组合回测...');
    try {
      const payload = {
        symbol: state.currentSymbol,
        pipeline: document.getElementById('bt-pipeline').value,
        strategy: document.getElementById('bt-strategy').value,
        start: document.getElementById('bt-start').value,
        end: document.getElementById('bt-end').value || undefined,
        stop_loss: document.getElementById('bt-stop-loss').value || undefined,
        capital: document.getElementById('dp-capital').value,
        fee: document.getElementById('dp-fee').value,
        lot: document.getElementById('dp-lot').value
      };
      const res = await runBacktest(payload);
      renderBacktestOutput(res);
      log('回测完成');
    } catch (e) {
      log(`回测失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  // 策略分析
  document.getElementById('btn-run-analysis')?.addEventListener('click', async () => {
    const symbol = document.getElementById('analysis-stock').value;
    const start = document.getElementById('analysis-start').value;
    const end = document.getElementById('analysis-end').value || new Date().toISOString().slice(0, 10);
    const maxDrawdown = parseFloat(document.getElementById('analysis-max-drawdown').value);
    const pipelines = document.getElementById('analysis-pipelines').value || undefined;
    const strategies = document.getElementById('analysis-strategies').value || undefined;
    setLoading(true, '正在进行季度策略分析...');
    try {
      const res = await analyzeStock({ symbol, start, end, save: false, max_drawdown: maxDrawdown, pipelines, strategies });
      renderAnalysisResult(res);
      log(`${symbol} 策略分析完成`);
    } catch (e) {
      log(`分析失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('btn-save-best-combo')?.addEventListener('click', async () => {
    const symbol = document.getElementById('analysis-stock').value;
    const start = document.getElementById('analysis-start').value;
    const end = document.getElementById('analysis-end').value || new Date().toISOString().slice(0, 10);
    const maxDrawdown = parseFloat(document.getElementById('analysis-max-drawdown').value);
    const pipelines = document.getElementById('analysis-pipelines').value || undefined;
    const strategies = document.getElementById('analysis-strategies').value || undefined;
    setLoading(true, '正在保存最佳组合...');
    try {
      const res = await analyzeStock({ symbol, start, end, save: true, max_drawdown: maxDrawdown, pipelines, strategies });
      renderAnalysisResult(res);
      loadBestComboForAnalysis();
      log(`${symbol} 最佳组合已保存`);
    } catch (e) {
      log(`保存失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  // 批量报告
  document.getElementById('btn-run-batch-report')?.addEventListener('click', async () => {
    const symbols = document.getElementById('batch-symbols').value || undefined;
    const start = document.getElementById('batch-start').value;
    const end = document.getElementById('batch-end').value || undefined;
    const maxDrawdown = parseFloat(document.getElementById('batch-max-drawdown').value);
    const capital = document.getElementById('batch-capital').value;
    const fee = document.getElementById('batch-fee').value;
    const lot = document.getElementById('batch-lot').value;
    setLoading(true, '正在生成批量报告...');
    try {
      const res = await runBatchReport({ symbols, start, end, max_drawdown: maxDrawdown, save: false, capital, fee, lot });
      renderBatchReport(res);
      log('批量报告生成完成');
    } catch (e) {
      log(`批量报告失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });

  document.getElementById('btn-save-batch-combos')?.addEventListener('click', async () => {
    const symbols = document.getElementById('batch-symbols').value || undefined;
    const start = document.getElementById('batch-start').value;
    const end = document.getElementById('batch-end').value || undefined;
    const maxDrawdown = parseFloat(document.getElementById('batch-max-drawdown').value);
    const capital = document.getElementById('batch-capital').value;
    const fee = document.getElementById('batch-fee').value;
    const lot = document.getElementById('batch-lot').value;
    setLoading(true, '正在保存批量最佳组合...');
    try {
      const res = await runBatchReport({ symbols, start, end, max_drawdown: maxDrawdown, save: true, capital, fee, lot });
      renderBatchReport(res);
      log('批量最佳组合已保存');
    } catch (e) {
      log(`保存失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });
}

/**
 * 渲染策略分析结果
 */
function renderAnalysisResult(res) {
  const summaryBox = document.getElementById('best-combo-summary');
  const rankBox = document.getElementById('analysis-rankings');
  if (!summaryBox || !rankBox) return;

  if (!res.success || !res.quarters) {
    summaryBox.textContent = '分析失败';
    return;
  }

  const lines = res.quarters.map(q => {
    const b = q.best;
    if (!b || b.total_return_pct === undefined) return `${q.quarter}: 无有效组合`;
    return `${q.quarter}: ${b.pipeline} + ${b.strategy} | 收益 ${b.total_return_pct.toFixed(2)}% | 回撤 ${b.max_drawdown_pct?.toFixed(2) || '--'}%`;
  });
  summaryBox.textContent = lines.join('\n');

  // 展示综合排名（后端返回 summary）
  if (res.summary && res.summary.length > 0) {
    const rows = res.summary
      .filter(r => r.total_return_pct > -900)
      .slice(0, 10)
      .map((r, i) => `#${i + 1} ${r.pipeline} + ${r.strategy}: 收益 ${r.total_return_pct.toFixed(2)}%, 回撤 ${r.max_drawdown_pct?.toFixed(2) || '--'}%, 夏普 ${r.sharpe?.toFixed(2) || '--'}`);
    rankBox.textContent = `综合排名（Top 10）：\n` + rows.join('\n');
  } else {
    rankBox.textContent = '无有效排名';
  }
}

/**
 * 渲染批量报告结果
 */
function renderBatchReport(res) {
  if (!res.success) {
    log(`批量报告失败：${res.message}`);
    return;
  }

  const analysisBox = document.getElementById('batch-analysis-table');
  const backtestBox = document.getElementById('batch-backtest-table');
  const decisionBox = document.getElementById('batch-decision-table');

  if (analysisBox) {
    const headers = ['代码', '最佳组合', '收益率', '最大回撤', '夏普', '交易次数', '放宽约束'];
    const rows = (res.analysis || [])
      .filter(r => !r.error)
      .map(r => [r.symbol, `${r.pipeline}+${r.strategy}`, `${r.total_return_pct.toFixed(2)}%`, `${r.max_drawdown_pct.toFixed(2)}%`, r.sharpe.toFixed(3), r.trade_count, r.relaxed ? '是' : '否']);
    analysisBox.innerHTML = renderHtmlTable(headers, rows);
  }

  if (backtestBox) {
    const headers = ['代码', 'Pipeline', 'Strategy', '收益率', '最大回撤', '夏普', '交易次数', '胜率', '最终资产', '手续费'];
    const rows = (res.backtest || []).map(r => [
      r.symbol, r.pipeline, r.strategy,
      `${r.total_return_pct.toFixed(2)}%`, `${r.max_drawdown_pct.toFixed(2)}%`,
      r.sharpe.toFixed(3), r.trade_count, `${r.win_rate.toFixed(2)}%`,
      formatMoney(r.final_value), formatMoney(r.total_fees)
    ]);
    backtestBox.innerHTML = renderHtmlTable(headers, rows);
  }

  if (decisionBox) {
    const headers = ['代码', '参考价', '目标仓位', '操作', '说明'];
    const rows = (res.decision || []).map(r => [
      r.symbol, r.open.toFixed(2), `${(r.target_position * 100).toFixed(1)}%`, r.action, r.note
    ]);
    decisionBox.innerHTML = renderHtmlTable(headers, rows);
  }
}

/**
 * 加载并显示策略分析页当前最佳组合
 */
async function loadBestComboForAnalysis() {
  const symbol = document.getElementById('analysis-stock')?.value || state.currentSymbol;
  try {
    const res = await getBestCombo(symbol);
    const box = document.getElementById('current-best-combo');
    if (!box) return;
    if (res.combo) {
      const c = res.combo;
      const m = c.metrics || {};
      const pipeline = c.pipeline_name || c.pipeline || 'N/A';
      const strategy = c.strategy_id || c.strategy || 'N/A';
      const tr = c.time_range || {};
      box.innerHTML = `<strong>${pipeline} + ${strategy}</strong><br>` +
        `配置: ${c.pipeline_config_id || 'N/A'}<br>` +
        `区间: ${tr.start || 'N/A'} ~ ${tr.end || 'N/A'}<br>` +
        `收益: ${m.total_return_pct?.toFixed(2) ?? '--'}%<br>` +
        `回撤: ${m.max_drawdown_pct?.toFixed(2) ?? '--'}%<br>` +
        `夏普: ${m.sharpe?.toFixed(3) ?? '--'}<br>` +
        `评估: ${c.last_evaluated?.slice(0, 10) || 'N/A'}`;
    } else {
      box.textContent = '暂无最佳组合，请先运行分析并保存。';
    }
  } catch (e) {
    log(`加载最佳组合失败：${e.message}`);
  }
}

/**
 * 加载并渲染基本面分析记录
 */
async function loadFundamentalRecords() {
  const tableBox = document.getElementById('fundamental-table');
  const contentBox = document.getElementById('fundamental-report-content');
  if (!tableBox) return;

  tableBox.textContent = '加载中...';
  if (contentBox) contentBox.textContent = '点击上方记录查看报告';

  try {
    const res = await getFundamentalRecords();
    if (!res.success || !res.records) {
      tableBox.textContent = '加载失败';
      return;
    }

    const records = res.records;
    if (!records.length) {
      tableBox.textContent = '暂无记录';
      return;
    }

    const table = document.createElement('table');
    table.className = 'fundamental-table';
    table.innerHTML = `
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>上次分析</th>
          <th>建议下次</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;

    const tbody = table.querySelector('tbody');
    records.forEach(r => {
      const tr = document.createElement('tr');
      tr.dataset.symbol = r.symbol;
      tr.style.cursor = 'pointer';
      const status = r.is_needed ? '需要分析' : '无需分析';
      const statusClass = r.is_needed ? 'status-needed' : 'status-ok';
      tr.innerHTML = `
        <td>${escapeHtml(r.symbol)}</td>
        <td>${escapeHtml(r.name)}</td>
        <td>${r.last_analysis_date || '从未分析'}</td>
        <td>${r.next_due_date}</td>
        <td><span class="${statusClass}">${status}</span></td>
      `;
      tr.addEventListener('click', () => loadFundamentalReport(r.symbol));
      tbody.appendChild(tr);
    });

    tableBox.innerHTML = '';
    tableBox.appendChild(table);
    log('基本面记录加载完成', 'log-box-fundamental');
  } catch (e) {
    tableBox.textContent = `加载失败：${e.message}`;
    log(`加载基本面记录失败：${e.message}`, 'log-box-fundamental');
  }
}

/**
 * 加载并显示某股票最新基本面报告
 */
async function loadFundamentalReport(symbol) {
  const contentBox = document.getElementById('fundamental-report-content');
  if (!contentBox) return;

  contentBox.textContent = '加载中...';
  try {
    const res = await getFundamentalReport(symbol);
    if (!res.success) {
      contentBox.textContent = `加载失败：${res.message || ''}`;
      return;
    }
    if (!res.has_report) {
      contentBox.textContent = `${symbol} 暂无已归档报告`;
      return;
    }
    contentBox.textContent = res.content;
    log(`已加载 ${symbol} 报告`, 'log-box-fundamental');
  } catch (e) {
    contentBox.textContent = `加载失败：${e.message}`;
    log(`加载 ${symbol} 报告失败：${e.message}`, 'log-box-fundamental');
  }
}

/* ============================================================
 * 组合决策视图
 * ========================================================== */

function plog(msg) {
  log(msg, 'log-box-portfolio');
}

async function loadPortfolioView() {
  // 填充持仓代码下拉
  const sel = document.getElementById('pf-pos-symbol');
  if (sel && sel.options.length === 0) {
    state.stocks.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.symbol;
      opt.textContent = `${s.symbol} ${s.name}`;
      sel.appendChild(opt);
    });
  }
  await loadPortfolioState();
  await loadPortfolioRiskProfile();
}

async function loadPortfolioState() {
  try {
    const res = await getPortfolioState();
    const st = res.state || {};
    document.getElementById('pf-cash').value = st.cash ?? 100000;
    document.getElementById('pf-lot').value = st.lot_size ?? 100;
    const equityBox = document.getElementById('portfolio-equity');
    if (equityBox) {
      equityBox.innerHTML = `预估总权益：<strong>${formatMoney(st.estimated_equity)}</strong> 元` +
        `<br>现金：${formatMoney(st.cash)} 元　更新：${st.updated_at || '--'}`;
    }
    renderPortfolioPositions(st);
  } catch (e) {
    plog(`加载组合状态失败：${e.message}`);
  }
}

function renderPortfolioPositions(st) {
  const box = document.getElementById('portfolio-positions-table');
  if (!box) return;
  const positions = st.positions || {};
  const prices = st.prices || {};
  const symbols = Object.keys(positions);
  if (symbols.length === 0) {
    box.textContent = '暂无持仓';
    return;
  }
  const headers = ['代码', '股数', '成本', '最新价', '市值', '操作'];
  const table = document.createElement('table');
  table.className = 'data-table';
  table.innerHTML = `<thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody></tbody>`;
  const tbody = table.querySelector('tbody');
  symbols.forEach(sym => {
    const p = positions[sym];
    const price = prices[sym];
    const mv = price ? p.shares * price : 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${escapeHtml(sym)}</td><td>${p.shares}</td>` +
      `<td>${Number(p.avg_cost).toFixed(2)}</td>` +
      `<td>${price ? Number(price).toFixed(2) : '--'}</td>` +
      `<td>${formatMoney(mv)}</td>` +
      `<td><button class="btn btn-danger btn-sm" data-remove="${escapeHtml(sym)}">🗑 移除</button></td>`;
    tbody.appendChild(tr);
  });
  box.innerHTML = '';
  box.appendChild(table);
  box.querySelectorAll('button[data-remove]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await deletePortfolioPosition(btn.dataset.remove);
        plog(`已移除 ${btn.dataset.remove}`);
        await loadPortfolioState();
      } catch (e) {
        plog(`移除失败：${e.message}`);
      }
    });
  });
}

async function loadPortfolioRiskProfile() {
  try {
    const res = await getPortfolioRiskProfile();
    const rp = res.risk_profile || {};
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    setVal('rp-max-total', rp.max_total_position);
    setVal('rp-max-single', rp.max_single_position);
    setVal('rp-max-late', rp.max_late_session_position);
    setVal('rp-min-cash', rp.min_cash_ratio);
    setVal('rp-dd-limit', rp.drawdown_limit_pct);
    setVal('rp-max-dd-events', rp.max_drawdown_events);
  } catch (e) {
    plog(`加载风险配置失败：${e.message}`);
  }
}

function renderPortfolioDecision(result) {
  const box = document.getElementById('portfolio-decision-output');
  if (!box) return;
  if (!result) { box.textContent = '无结果'; return; }
  const p = result.portfolio || {};
  const parts = [];
  parts.push(`<p>模式：<strong>${result.mode}</strong>　时间：${result.timestamp || '--'}</p>`);
  parts.push(`<p>现金：${formatMoney(p.cash)}　预估权益：${formatMoney(p.estimated_equity)}　` +
    `当前敞口：${((p.current_stock_exposure || 0) * 100).toFixed(1)}%　` +
    `目标敞口：${((p.target_stock_exposure || 0) * 100).toFixed(1)}%　` +
    `交易后现金：${formatMoney(p.cash_after_trades)}</p>`);

  // 订单建议（带买卖标签）
  parts.push('<h4>📋 订单建议</h4>');
  const orders = result.orders || [];
  if (!orders.length) {
    parts.push('<p class="hint">当前无建议交易（已满足风险与仓位约束）。</p>');
  } else {
    const orderBody = orders.map(o => {
      const tagClass = o.action === 'buy' ? 'tag-buy' : (o.action === 'sell' ? 'tag-sell' : 'tag-hold');
      const tagText = o.action === 'buy' ? '买入' : (o.action === 'sell' ? '卖出' : '持有');
      return `<tr>
        <td><span class="tag ${tagClass}">${tagText}</span></td>
        <td>${escapeHtml(o.symbol)}</td>
        <td>${o.shares}</td>
        <td>${Number(o.price).toFixed(2)}</td>
        <td>${formatMoney(o.estimated_cash_change)}</td>
        <td>${escapeHtml(o.reason || '')}</td>
      </tr>`;
    }).join('');
    parts.push(`<table class="data-table"><thead><tr>
      <th>操作</th><th>代码</th><th>股数</th><th>价格</th><th>现金变动</th><th>理由</th>
      </tr></thead><tbody>${orderBody}</tbody></table>`);
  }

  // 候选（选中 / 拒绝分开，带行高亮）
  const cands = result.candidates || [];
  const selected = cands.filter(c => c.selected);
  const rejected = cands.filter(c => !c.selected);
  const candCells = c => `
    <td>${c.rank ?? '-'}</td>
    <td>${escapeHtml(c.symbol)}</td>
    <td>${escapeHtml((c.prediction && c.prediction.signal) || 'N/A')}</td>
    <td>${c.risk ? c.risk.max_drawdown_pct + '%' : '--'}</td>
    <td>${c.risk ? c.risk.drawdown_events : '--'}</td>`;

  parts.push('<h4>✅ 选中候选（风险优先排序）</h4>');
  if (!selected.length) {
    parts.push('<p class="hint">无通过风险过滤的候选。</p>');
  } else {
    const body = selected.map(c => `<tr class="row-selected">${candCells(c)}<td>${c.score ? c.score.final_rank : '--'}</td></tr>`).join('');
    parts.push(`<table class="data-table"><thead><tr>
      <th>排名</th><th>代码</th><th>信号</th><th>最大回撤</th><th>回撤事件</th><th>final_rank</th>
      </tr></thead><tbody>${body}</tbody></table>`);
  }
  if (rejected.length) {
    parts.push('<h4>⛔ 已拒绝候选</h4>');
    const body = rejected.map(c => `<tr class="row-rejected">${candCells(c)}<td>${escapeHtml(c.rejected_reason || '')}</td></tr>`).join('');
    parts.push(`<table class="data-table"><thead><tr>
      <th>排名</th><th>代码</th><th>信号</th><th>最大回撤</th><th>回撤事件</th><th>拒绝原因</th>
      </tr></thead><tbody>${body}</tbody></table>`);
  }

  // 尾盘计划
  const late = result.late_session_plan || [];
  if (late.length) {
    parts.push('<h4>🌙 尾盘次日离场计划</h4>');
    parts.push(renderHtmlTable(['代码', '入场价', '止盈价', '兜底'],
      late.map(pl => [pl.symbol, Number(pl.entry_price).toFixed(2),
        Number(pl.take_profit_price).toFixed(2), pl.fallback_exit])));
  }
  box.innerHTML = parts.join('');
}

function bindPortfolioEvents() {
  document.getElementById('btn-save-pf-cash')?.addEventListener('click', async () => {
    try {
      const cash = parseFloat(document.getElementById('pf-cash').value);
      await putPortfolioState({ cash });
      plog(`现金已设为 ${formatMoney(cash)}`);
      await loadPortfolioState();
    } catch (e) {
      plog(`保存现金失败：${e.message}`);
    }
  });

  document.getElementById('btn-add-pf-position')?.addEventListener('click', async () => {
    try {
      const symbol = document.getElementById('pf-pos-symbol').value;
      const shares = parseInt(document.getElementById('pf-pos-shares').value, 10);
      const costRaw = document.getElementById('pf-pos-cost').value;
      const payload = { symbol, shares };
      if (costRaw !== '') payload.avg_cost = parseFloat(costRaw);
      await setPortfolioPosition(payload);
      plog(`${symbol} 持仓已更新`);
      await loadPortfolioState();
    } catch (e) {
      plog(`更新持仓失败：${e.message}`);
    }
  });

  document.getElementById('btn-save-risk-profile')?.addEventListener('click', async () => {
    try {
      const num = id => {
        const v = document.getElementById(id).value;
        return v === '' ? undefined : parseFloat(v);
      };
      const payload = {
        max_total_position: num('rp-max-total'),
        max_single_position: num('rp-max-single'),
        max_late_session_position: num('rp-max-late'),
        min_cash_ratio: num('rp-min-cash'),
        drawdown_limit_pct: num('rp-dd-limit'),
        max_drawdown_events: num('rp-max-dd-events')
      };
      Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);
      await putPortfolioRiskProfile(payload);
      plog('风险配置已保存');
      await loadPortfolioRiskProfile();
    } catch (e) {
      plog(`保存风险配置失败：${e.message}`);
    }
  });

  document.getElementById('pf-mode')?.addEventListener('change', () => {
    const mode = document.getElementById('pf-mode').value;
    const box = document.getElementById('pf-quote-inputs');
    if (box) box.style.display = mode === 'close_after_market' ? 'none' : 'block';
  });

  document.getElementById('btn-run-portfolio-decide')?.addEventListener('click', async () => {
    setLoading(true, '正在生成组合决策...');
    try {
      const mode = document.getElementById('pf-mode').value;
      const symbolsRaw = document.getElementById('pf-symbols').value.trim();
      const payload = { mode };
      if (symbolsRaw) payload.symbols = symbolsRaw;
      const quoteRaw = document.getElementById('pf-quote-json').value.trim();
      if (quoteRaw && mode !== 'close_after_market') {
        let parsed;
        try {
          parsed = JSON.parse(quoteRaw);
        } catch (err) {
          plog(`行情 JSON 解析失败：${err.message}`);
          setLoading(false);
          return;
        }
        if (mode === 'open_realtime') payload.open_prices = parsed;
        else payload.quotes = parsed;
      }
      const res = await portfolioDecide(payload);
      renderPortfolioDecision(res.result);
      plog('组合决策完成');
    } catch (e) {
      plog(`组合决策失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  });
}

/**
 * 初始化
 */
async function init() {
  document.getElementById('current-date').textContent = new Date().toLocaleDateString('zh-CN');

  await initStockSelector();
  await initPipelineStrategySelectors();
  await loadStockChart(state.currentSymbol);
  await loadDashboardBestCombo();

  bindEvents();
  bindPortfolioEvents();
  log('页面加载完成');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
