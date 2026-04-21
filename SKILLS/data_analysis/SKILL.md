---
name: data_analysis
description: >
  Use when the research involves tabular data, statistical analysis,
  pandas/numpy operations, correlation studies, or quantitative findings.
tags: [data, analysis, statistics, pandas, csv, excel]
version: 1.0
---

# Data Analysis Skill

## When to activate this skill
- Query mentions numbers, statistics, trends, correlations, distributions
- User provides CSV or Excel files
- Research requires quantitative evidence
- Need to validate claims with data

## Recommended tool sequence
1. `data_schema(file_path)` to understand structure
2. `data_summary(file_path)` for statistical overview
3. `data_head(file_path)` to preview data
4. `execute_python(pandas_script)` for custom analysis
5. `search_from_indexes()` to cross-reference with indexed knowledge
6. Update scratch pad with key statistics found

## Prompting guidance
- Ask for Python pandas code to explore the data
- Request interpretation of statistical outputs
- Ask to flag outliers and anomalies
- Use correlation matrices before drawing causal conclusions

## Common pitfalls to avoid
- Do not confuse correlation with causation
- Always check for missing data before computing stats
- Normalize distributions before comparing across datasets
- Beware of Simpson's paradox in grouped data
