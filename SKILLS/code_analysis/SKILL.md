---
name: code_analysis
description: >
  Use when research involves analyzing code, software architecture,
  programming paradigms, or requires writing code for data processing.
tags: [code, programming, software, analysis, python]
version: 1.0
---

# Code Analysis Skill

## When to activate this skill
- Query involves software or code concepts
- Need to write Python scripts for data processing
- Research requires understanding algorithms or architectures
- Need to execute code to verify findings

## Recommended tool sequence
1. `execute_python(code)` for running analysis scripts
2. Review outputs and error messages
3. Iterate on code if errors occur
4. Index code findings and results

## Prompting guidance
- Write clean, well-commented Python code
- Use try/except for error handling in scripts
- Print results in readable formats (tables, summaries)
- Break complex analysis into small verifiable steps

## Common pitfalls to avoid
- Do not run untrusted code without sandboxing
- Handle large datasets with chunked processing
- Validate data types before operations
- Always check for edge cases in algorithms
