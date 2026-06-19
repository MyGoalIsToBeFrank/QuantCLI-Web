---
name: fundamental-analysis
description: >
  Guide for interacting with the project's fundamental analysis CLI module.
  Use when the user or a scheduled task asks you to perform fundamental analysis
  on a registered stock, check whether analysis is due, generate the agent prompt,
  or write back a fundamental analysis report.
---

# Fundamental Analysis Skill

This skill describes how to use the `strategy fundamental` CLI commands to
coordinate fundamental analysis for registered stocks.

## When to Use

- A daily check asks whether any registered stock needs fundamental analysis.
- The user requests a fundamental analysis report for a stock.
- You need to record or retrieve a previously generated fundamental analysis report.

## Registered Stocks

Run the following command to see available stocks:

```bash
strategy list stocks
```

Current registered stocks:

- `002156.SZ` 通富微电（半导体封装）
- `601225.SS` 陕西煤业（煤炭开采）
- `300308.SZ` 中际旭创（半导体光模块）
- `600460.SH` 士兰微（半导体 IDM）
- `605358.SH` 立昂微（半导体硅片）
- `000725.SZ` 京东方A（显示面板）
- `002185.SZ` 华天科技（半导体封测）
- `AMD` AMD（美股半导体设计）

## Workflow

### Step 1: Check if Analysis is Needed

```bash
strategy fundamental check -s <symbol>
```

- Exit code `0` means analysis is needed (never analyzed or due date reached).
- Exit code `1` means analysis is not yet needed.
- The command prints last analysis date, next due date, and status.

### Step 2: Generate the Agent Prompt (Optional)

If analysis is needed, you can get a ready-to-use prompt to send to another AI
agent or use yourself:

```bash
strategy fundamental prompt -s <symbol>
```

This prompt references the external comprehensive analysis skill.

Set the environment variable:

```bash
set STOCK_BASIC_ANALYSIS_SKILL=C:\path\to\stock-basic-analysis\SKILL.md
```

Or place the SKILL file at:

```text
.agents/skills/stock-basic-analysis/SKILL.md
```

Open and follow that SKILL file for the actual fundamental/technical analysis
methodology, scoring model, and report structure.

### Step 3: Perform Analysis

Use the external `stock-basic-analysis` SKILL to perform data acquisition,
fundamental scoring, technical analysis, trend extraction, prediction, and report
generation. Save the report as a Markdown file.

### Step 4: Write Back the Report

```bash
strategy fundamental report -s <symbol> -f <path_to_report.md>
```

The CLI will:

1. Copy the report into `reports/fundamental/<symbol>/<date>_report.md`.
2. Update `data/fundamental_records.json` with the analysis date and report path.

### Step 5: Verify or Read the Report

```bash
strategy fundamental show -s <symbol>
strategy fundamental list
```

The Web UI "基本面记录" view also loads these records in read-only mode.

## Report Requirements

The report written back via `strategy fundamental report` should be a Markdown
file containing at least:

1. Executive summary and final rating.
2. Four-dimension fundamental scores (profitability, growth, financial health,
   valuation) if available.
3. Key financial metrics and peer comparison.
4. Technical snapshot (optional but recommended).
5. Trend/prediction summary.
6. Risk warnings and investment recommendation.

## Batch Check Example

```bash
#!/bin/bash
for symbol in 002156.SZ 601225.SS 300308.SZ 600460.SH 605358.SH 000725.SZ 002185.SZ AMD; do
  if strategy fundamental check -s "$symbol"; then
    strategy fundamental prompt -s "$symbol" > "/tmp/${symbol}_prompt.txt"
    echo "Analysis needed for $symbol; prompt saved."
  fi
done
```

## Reference

- External methodology: `D:\BaiduSyncdisk\Pantanimitas\.agents\skills\stock-basic-analysis\SKILL.md`
- CLI source: `src/cli/commands/fundamental_cmd.py`
- Records manager: `src/fundamental/records.py`
- Archived reports: `reports/fundamental/`
- Project docs: `README.md`, `AGENTS.md`
