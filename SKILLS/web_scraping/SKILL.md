---
name: web_scraping
description: >
  Use when the research requires gathering information from web pages,
  handling JavaScript-rendered content, and extracting clean text from HTML.
tags: [web, scraping, html, crawl, fetch]
version: 1.0
---

# Web Scraping Skill

## When to activate this skill
- Query requires information from specific websites
- Research involves crawling multiple pages
- Content may be behind JavaScript rendering
- Need to extract structured data from web pages

## Recommended tool sequence
1. `searxng_search(query)` to find relevant URLs
2. Fetch pages via the web fetcher (HTTP first, browser fallback)
3. Extract clean text using trafilatura
4. Index extracted content immediately (INDEX-AS-YOU-GO)
5. Update scratch pad with key findings

## Prompting guidance
- Prioritize official sources, documentation, and academic papers
- Score URLs by domain authority and content length
- Use browser fallback for sites with heavy JavaScript

## Common pitfalls to avoid
- Do not trust page titles alone; verify content quality
- Avoid crawling too many pages from a single domain
- Skip binary files and very large pages
- Check for paywalls and cookie walls that block content
