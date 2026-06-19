/**
 * kline.js
 * 基于 ECharts 的 K 线渲染模块
 */

/**
 * 计算简单移动平均线（SMA）
 * @param {number} dayCount 周期
 * @param {Array<object>} data K 线数组，元素需包含 close
 * @returns {Array<number|string>} MA 数组，数据不足时返回 '-'
 */
function calculateMA(dayCount, data) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < dayCount - 1) {
      result.push('-');
      continue;
    }
    let sum = 0;
    for (let j = 0; j < dayCount; j++) {
      sum += data[i - j].close;
    }
    result.push(parseFloat((sum / dayCount).toFixed(4)));
  }
  return result;
}

/**
 * 渲染单个 K 线图
 * @param {string} containerId 容器 DOM id
 * @param {string} title 图表标题（仅用于内部标识）
 * @param {Array<object>} klineData K 线数据
 * @param {Array<number|string>} ma5 MA5
 * @param {Array<number|string>} ma20 MA20
 * @param {Array<number|string>} ma60 MA60
 * @param {Array<object>} volumes ECharts 成交量数据项（含颜色）
 * @param {Array<object>} trades 买卖点标记 {date, price, type: 'buy'|'sell'}
 */
function renderChart(containerId, title, klineData, ma5, ma20, ma60, volumes, trades = []) {
  const dom = document.getElementById(containerId);
  if (!dom) return;

  let chart = echarts.getInstanceByDom(dom);
  if (!chart) {
    chart = echarts.init(dom, 'dark');
  }

  const dates = klineData.map(item => item.date);
  const values = klineData.map(item => [item.open, item.close, item.low, item.high]);

  // 买卖点标注：标签远离 K 线，箭头在距 K 线一定距离处指向 K 线，不覆盖蜡烛
  const tradeMarkLines = trades.map(t => {
    const isBuy = t.type === 'buy';
    const color = isBuy ? CONFIG.COLORS.up : CONFIG.COLORS.down;
    const labelOffset = t.price * 0.28;  // 标签距离 K 线 28%
    const arrowOffset = t.price * 0.12;  // 箭头距离 K 线 12%，指向但不贴箱体
    const labelPrice = isBuy ? t.price - labelOffset : t.price + labelOffset;
    const arrowPrice = isBuy ? t.price - arrowOffset : t.price + arrowOffset;
    const shares = t.shares || 0;
    return [
      {
        coord: [t.date, labelPrice],
        symbol: 'none',
        lineStyle: { color: color, width: 1, type: 'dashed' },
        label: {
          show: true,
          position: 'start',
          formatter: `${isBuy ? '买入' : '卖出'} ${shares}股\n@ ${Number(t.price).toFixed(2)}`,
          color: color,
          fontSize: 10,
          backgroundColor: 'rgba(22, 27, 34, 0.8)',
          borderColor: color,
          borderWidth: 1,
          borderRadius: 3,
          padding: [2, 4]
        }
      },
      {
        coord: [t.date, arrowPrice],
        symbol: 'arrow',
        symbolSize: 10,
        lineStyle: { color: color, width: 1 }
      }
    ];
  });

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(22, 27, 34, 0.95)',
      borderColor: '#30363d',
      textStyle: { color: '#c9d1d9' }
    },
    grid: [
      { left: '10%', right: '8%', height: '55%', top: '10%' },
      { left: '10%', right: '8%', top: '72%', height: '16%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#30363d' } },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
        splitLine: { lineStyle: { color: '#21262d' } },
        position: 'right'
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        start: 50,
        end: 100,
        bottom: '2%',
        height: 16,
        borderColor: '#30363d',
        fillerColor: 'rgba(88, 166, 255, 0.2)'
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: values,
        itemStyle: {
          color: CONFIG.COLORS.up,
          color0: CONFIG.COLORS.down,
          borderColor: CONFIG.COLORS.up,
          borderColor0: CONFIG.COLORS.down
        },
        markLine: {
          symbol: ['none', 'arrow'],
          data: tradeMarkLines,
          animation: false
        }
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: CONFIG.COLORS.ma5 }
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: CONFIG.COLORS.ma20 }
      },
      {
        name: 'MA60',
        type: 'line',
        data: ma60,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: CONFIG.COLORS.ma60 }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes
      }
    ]
  };

  chart.setOption(option, true);
}

/**
 * 全局缓存 K 线数据，供回测动画使用
 */
window.KLINE_DATA = { amd: [], tongfu: [] };

/**
 * 接收 /api/data 返回的数据并渲染两张 K 线图
 * @param {object} data {amd: [...], tongfu: [...]}
 */
function updateCharts(data) {
  window.KLINE_DATA = data || { amd: [], tongfu: [] };

  const symbols = [
    { key: 'amd', title: 'AMD' },
    { key: 'tongfu', title: '通富微电' }
  ];

  symbols.forEach(({ key, title }) => {
    const arr = data[key] || [];
    if (!arr.length) return;

    const ma5 = calculateMA(5, arr);
    const ma20 = calculateMA(20, arr);
    const ma60 = calculateMA(60, arr);

    const volumes = arr.map(item => {
      const isUp = item.close >= item.open;
      return {
        value: item.volume,
        itemStyle: {
          color: isUp ? CONFIG.COLORS.volumeUp : CONFIG.COLORS.volumeDown
        }
      };
    });

    renderChart(`${key}-chart`, title, arr, ma5, ma20, ma60, volumes);
  });
}

/**
 * 回测动画：将通富微电 K 线图演进至指定日期，并标记买卖信号
 * @param {number} currentIndex 当前回测记录索引
 * @param {Array<object>} records 回测记录数组
 */
function updateBacktestKline(currentIndex, records) {
  const allData = window.KLINE_DATA.tongfu || [];
  if (!allData.length || !records.length) return;

  const currentDate = records[currentIndex].date;
  // 找到 K 线数据中对应日期的索引
  let klineIdx = allData.findIndex(item => item.date === currentDate);
  if (klineIdx < 0) klineIdx = currentIndex;

  // 截取到当前日期的数据
  const sliced = allData.slice(0, klineIdx + 1);

  // 收集到当前日期为止的交易信号（首条相对初始空仓 0 股）
  const trades = [];
  for (let i = 0; i <= currentIndex; i++) {
    const r = records[i];
    const prevShares = i > 0 ? records[i - 1].shares : 0;
    if (r.shares !== prevShares) {
      trades.push({
        date: r.date,
        price: r.price,
        type: r.shares > prevShares ? 'buy' : 'sell',
        shares: Math.abs(r.shares - prevShares)
      });
    }
  }

  const ma5 = calculateMA(5, sliced);
  const ma20 = calculateMA(20, sliced);
  const ma60 = calculateMA(60, sliced);
  const volumes = sliced.map(item => ({
    value: item.volume,
    itemStyle: {
      color: item.close >= item.open ? CONFIG.COLORS.volumeUp : CONFIG.COLORS.volumeDown
    }
  }));

  renderChart('tongfu-chart', '通富微电', sliced, ma5, ma20, ma60, volumes, trades);
}

/**
 * 渲染资金曲线图（回测可视化）
 * @param {string} containerId 容器 DOM id
 * @param {Array<object>} records 回测记录数组
 * @param {number} highlightIndex 高亮索引
 */
function renderPortfolioChart(containerId, records, highlightIndex = -1) {
  const dom = document.getElementById(containerId);
  if (!dom) return;

  let chart = echarts.getInstanceByDom(dom);
  if (!chart) {
    chart = echarts.init(dom, 'dark');
  }

  const dates = records.map(r => r.date);
  const values = records.map(r => r.portfolio);
  const initial = values[0];

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(22, 27, 34, 0.95)',
      borderColor: '#30363d',
      textStyle: { color: '#c9d1d9' },
      formatter: params => {
        const idx = params[0].dataIndex;
        const r = records[idx];
        return `${r.date}<br/>总资产: ${r.portfolio.toFixed(2)}<br/>收益率: ${((r.portfolio / initial - 1) * 100).toFixed(2)}%`;
      }
    },
    grid: { left: '10%', right: '8%', top: '12%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#30363d' } },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { lineStyle: { color: '#30363d' } },
      splitLine: { lineStyle: { color: '#21262d' } },
      position: 'right'
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%', height: 14, borderColor: '#30363d', fillerColor: 'rgba(88, 166, 255, 0.2)' }
    ],
    series: [
      {
        name: '总资产',
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#ffd666' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255, 214, 102, 0.3)' },
              { offset: 1, color: 'rgba(255, 214, 102, 0.02)' }
            ]
          }
        },
        markLine: highlightIndex >= 0 ? {
          animation: false,
          symbol: 'none',
          data: [{ xAxis: highlightIndex }],
          lineStyle: { color: '#58a6ff', type: 'dashed' }
        } : undefined
      }
    ]
  };

  chart.setOption(option, true);
}

/**
 * 渲染单只股票 K 线图（新 UI 统一入口）
 * @param {string} containerId 容器 DOM id
 * @param {Array<object>} arr K 线数据数组
 * @param {Array<object>} trades 可选买卖点标记
 */
function renderStockChart(containerId, arr, trades = []) {
  if (!arr || !arr.length) return;

  const ma5 = calculateMA(5, arr);
  const ma20 = calculateMA(20, arr);
  const ma60 = calculateMA(60, arr);

  const volumes = arr.map(item => ({
    value: item.volume,
    itemStyle: {
      color: item.close >= item.open ? CONFIG.COLORS.volumeUp : CONFIG.COLORS.volumeDown
    }
  }));

  const title = document.getElementById('chart-title')?.textContent || 'K 线图';
  renderChart(containerId, title, arr, ma5, ma20, ma60, volumes, trades);
}

// 暴露到全局，供 app.js 调用
window.updateCharts = updateCharts;
window.renderStockChart = renderStockChart;
window.renderPortfolioChart = renderPortfolioChart;
