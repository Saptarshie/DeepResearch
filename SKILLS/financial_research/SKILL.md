---
name: financial_research
description: >
  Use when the research involves financial analysis, market data,
  company financials, investment analysis, or economic indicators.
tags: [finance, economics, market, investment, company, stocks]
version: 1.0
---

# Financial Research Skill

## When to activate this skill
- Query mentions companies, markets, stocks, revenue, profits
- User provides financial spreadsheets or reports
- Research requires understanding economic indicators
- Need to analyze financial trends or company performance

## Recommended tool sequence
1. `searxng_search(query)` for financial news and reports
2. `ingest_document(report.pdf)` for annual/quarterly reports
3. `data_summary(file_path)` for financial spreadsheets
4. `execute_python(financial_analysis_script)` for calculations
5. Cross-reference with indexed economic data

## Prompting guidance
- Distinguish between revenue, profit, and cash flow
- Always note the time period for financial figures
- Compare metrics year-over-year for trends
- Consider inflation-adjusted figures for long-term comparisons

## Common pitfalls to avoid
- Do not confuse GAAP and non-GAAP metrics
- Beware of survivorship bias in historical data
- Note currency differences when comparing international companies
- Check for one-time charges that distort quarterly results
