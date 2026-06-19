# 前端构建完成报告

生成时间：2026-06-18

## 已完成文件

| 文件路径 | 说明 |
|---------|------|
| `src/frontend/index.html` | 主页面，包含顶部导航、K 线展示区、控制面板、批量报告视图 |
| `src/frontend/css/style.css` | 深色交易风格样式，支持响应式布局 |
| `src/frontend/js/config.js` | 前端默认配置（后端地址、颜色主题等） |
| `src/frontend/js/api.js` | 封装所有后端 API 调用，统一错误处理 |
| `src/frontend/js/kline.js` | ECharts K 线渲染，含 MA5/MA20/MA60、成交量、买卖点标记 |
| `src/frontend/js/app.js` | 页面主逻辑、视图切换、按钮事件、批量报告渲染 |
| `src/frontend/assets/loading.svg` | SVG loading 动画 |

## 主要功能点

### 顶部导航栏

- 项目名称、当前日期显示
- 股票选择器（从 `/api/stocks` 加载）
- 视图切换：仪表盘、策略分析、批量报告、基本面记录

### 仪表盘视图

- **K 线图**：单只股票 ECharts K 线，红涨绿跌，支持缩放、拖拽、十字光标、tooltip，叠加 MA5/MA20/MA60 与成交量。
- **当前最佳组合**：从 `/api/best_combo` 加载，显示 Pipeline + Strategy、收益率、回撤、夏普、评估日期。
- **T日决策**：输入今日开盘价，点击“运行决策”，支持自定义初始资金、手续费、每手股数。
- **组合回测**：选择 Pipeline/Strategy、起止日期、回撤止损，调用 `/api/backtest` 查看结果。

### 策略分析视图

- 选择股票、日期区间、最大回撤约束。
- 可选限定 Pipeline/Strategy 范围。
- 调用 `/api/analyze` 获取季度最佳组合与综合排名。
- 支持保存最佳组合到 `data/best_combos.json`。

### 批量报告视图（新增）

- 设置日期区间、最大回撤约束、资金/手续费/手数、限定股票列表。
- 调用 `/api/batch_report` 生成：
  - 批量分析结果表
  - 批量回测结果表
  - 今日批量决策表
- 支持保存最佳组合。

### 基本面记录视图

- 只读加载 `/api/fundamental_records`。
- 点击记录查看 `/api/fundamental_report` 返回的 Markdown 报告。
- 不在 Web 端执行分析。

### API 与交互

- 所有后端接口通过 `fetch` 封装。
- 基地址：`http://127.0.0.1:5000`（可在 `src/frontend/js/config.js` 修改）。
- 统一 loading 遮罩与错误日志提示。

### 响应式适配

- 在 1920×1080 与 1366×768 下均可使用。
- 小屏自动切换为上下布局。

## 使用方式

1. 启动后端 Flask 服务：`scripts\start.bat` 或 `.venv\Scripts\python.exe src\api_server.py`。
2. 浏览器访问 `http://127.0.0.1:5000`。
3. 页面自动加载股票池、K 线、最佳组合与配置。

## 验证

- `node --check src/frontend/js/*.js` 通过。
- 后端 API 冒烟测试通过（`/api/stocks`、`/api/best_combo`、`/api/decide_stock`、`/api/backtest`、`/api/batch_report`）。
- 首页 HTML 正常加载，新视图元素完整。
