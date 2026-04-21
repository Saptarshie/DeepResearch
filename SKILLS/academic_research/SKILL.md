---
name: academic_research
description: >
  Use when the research requires academic rigor, paper citations,
  understanding of scientific methods, and literature review techniques.
tags: [academic, research, papers, science, citations, literature]
version: 1.0
---

# Academic Research Skill

## When to activate this skill
- Query involves scientific topics or academic concepts
- Research requires peer-reviewed sources
- Need to understand methodologies and experimental results
- Literature review or meta-analysis is required

## Recommended tool sequence
1. `searxng_search(query, categories="science")` for academic results
2. `ingest_document(paper.pdf)` to parse research papers
3. Extract key claims, methods, and conclusions
4. `search_from_indexes()` to compare with prior findings
5. Note contradictions between papers in scratch pad

## Prompting guidance
- Focus on methodology sections for evidence quality
- Track citation chains between papers
- Distinguish between empirical findings and theoretical claims
- Note sample sizes and statistical significance

## Common pitfalls to avoid
- Do not treat preprints as peer-reviewed findings
- Beware of publication bias toward positive results
- Check for retracted papers
- Note funding sources for potential conflicts of interest
