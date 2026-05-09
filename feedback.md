Here is a comprehensive performance review of the deep research project, categorized by severity:

---

## Critical Bottlenecks (Fix Immediately)

### 1. **Sequential Document Fetching in `deep_search.py`**

**Location:** `deep_search.py`, main fetch loop (~line 88)

**Problem:** Documents are fetched one-at-a-time in a `while` loop. With `max_docs=100` and a 2s average fetch time, this alone takes **~3.3 minutes** of pure serial I/O waiting.

```python
while not frontier.empty() and len(docs) < cfg.max_docs:
    item = frontier.pop()
    fetched = await fetcher.fetch(item.url)  # Serial network I/O
```

**Fix:** Use bounded concurrent fetching with `asyncio.Semaphore`:

```python
semaphore = asyncio.Semaphore(10)  # Configurable concurrency

async def fetch_one(item):
    async with semaphore:
        # fetch, extract, dedup logic
        ...

# Run batches concurrently
batch = [frontier.pop() for _ in range(min(10, frontier.size()))]
results = await asyncio.gather(*[fetch_one(i) for i in batch], return_exceptions=True)
```

---

### 2. **Synchronous LLM Calls Blocking the Async Event Loop**

**Location:** `planner.py`, `critic.py`, `indexer.py`, `overview_builder.py`, `report_builder.py`

**Problem:** All LLM calls use synchronous clients (`anthropic.Anthropic`, `openai.OpenAI`) called directly from async code. When `critic.find_gaps()` or `indexer.process_docs()` runs, the **entire event loop freezes**—no other coroutine can progress.

**Fix:** Run synchronous LLM calls in a thread pool:

```python
# In deep_search.py or LLMClient
loop = asyncio.get_running_loop()
plan = await loop.run_in_executor(None, planner.make_plan, query)
gap_report = await loop.run_in_executor(None, critic.find_gaps, query, docs)
```

Even better, migrate to `anthropic.AsyncAnthropic` and `openai.AsyncOpenAI` natively.

---

### 3. **O(n²) String Concatenation in LLM Streaming**

**Location:** `llm_client.py`, `AnthropicClient.generate()` and `OpenAIClient.generate()`

**Problem:** Building response text with `+=` in a loop is quadratic time for large outputs:

```python
response_text = ""
for chunk in stream:
    response_text += chunk.delta.text  # O(n²) reallocations
```

**Fix:** Use `io.StringIO` or collect chunks in a list and join:

```python
chunks = []
for chunk in stream:
    if hasattr(chunk.delta, "text"):
        chunks.append(chunk.delta.text)
return "".join(chunks)
```

---

### 4. **Double (Triple) HTML Parsing in `extractor.py`**

**Location:** `extractor.py`, `extract_document()`

**Problem:** The function parses the same HTML up to 3 times:

1. `trafilatura.extract()` — parses HTML
2. `trafilatura.bare_extraction()` — parses HTML again
3. `lxml.html.fromstring()` — parses HTML a third time (fallback title)

**Fix:** Parse once with `lxml`, pass the tree to trafilatura, or use `bare_extraction` only and derive text from it:

```python
meta_raw = bare_extraction(html, url=url, with_metadata=True)
text = meta_raw.get("text", "") if isinstance(meta_raw, dict) else ""
```

---

## High Severity Bottlenecks

### 5. **Indexer: Sequential LLM Call Per Document**

**Location:** `indexer.py`, `process_docs()`

**Problem:** Each of N documents triggers a separate LLM call that includes the **entire growing topics hierarchy** and scratch pad. This is O(n²) in context size and makes N sequential network round-trips. For 100 docs, this dominates total runtime.

**Fix:** Batch documents. Send 5–10 documents per LLM call, or use a cheaper embedding-based clustering step before invoking the LLM indexer.

---

### 6. **Overview Builder: Exponential LLM Calls**

**Location:** `overview_builder.py`, `build_overview()`

**Problem:** Recursively calls the LLM for **every directory node** in the hierarchy. A hierarchy with 50 nodes = 50 LLM calls. Each call includes all child summaries, so context balloons.

**Fix:** Use a bottom-up approach without LLM calls for intermediate nodes—simply concatenate and summarize with a deterministic algorithm, or only call the LLM at the top level.

---

### 7. **No Concurrency Limits on Search Queries**

**Location:** `deep_search.py`, `asyncio.gather(*[_search_one(q) for q in plan.queries])`

**Problem:** If the planner generates 20 queries, all 20 hit SearxNG simultaneously. This can overwhelm the instance, cause rate limiting, or exhaust local file descriptors.

**Fix:** Use `asyncio.Semaphore` or `asyncio.gather` with chunked batches:

```python
async def search_batch(queries, limit=5):
    semaphore = asyncio.Semaphore(limit)
    async def bounded(q):
        async with semaphore:
            return await searx.search(q)
    return await asyncio.gather(*[bounded(q) for q in queries])
```

---

### 8. **Playwright Browser Launched Lazily, Not Reused Optimally**

**Location:** `fetcher.py`, `fetch_browser()`

**Problem:** A new page is created per browser fetch. Page creation in Playwright is expensive (~100–300ms). With many JS-heavy sites, this adds up.

**Fix:** Maintain a pool of pages or reuse a single page (with proper cleanup/navigate):

```python
# Reuse one page instance
if not hasattr(self, '_page') or self._page.is_closed():
    self._page = await browser.new_page()
await self._page.goto(url, wait_until="networkidle")
```

---

### 9. **Blocking `queue.PriorityQueue` in Async Context**

**Location:** `frontier.py`

**Problem:** `queue.PriorityQueue` uses threading locks internally. While it won't deadlock in single-threaded asyncio, it is unnecessary overhead and semantically wrong.

**Fix:** Use `asyncio.PriorityQueue` or a simple `heapq`-based structure wrapped for async.

---

## Medium Severity Bottlenecks

### 10. **Expensive Duplicate Check Normalization**

**Location:** `deep_search.py`, `_normalize_text()`

**Problem:** `text.lower().split()` and `" ".join(...)` materializes the entire document into a new string just for hashing. For large documents this is memory and CPU overhead.

**Fix:** Use a faster hash on raw or minimally processed text, or skip normalization:

```python
content_hash = hashlib.md5(text[:5000].encode()).hexdigest()  # Sample-based dedup
```

---

### 11. **Report Builder: Synchronous File I/O and Traversal**

**Location:** `report_builder.py`, `build_report()`

**Problem:** The entire report construction is synchronous blocking I/O (reading many `.md` files) mixed with LLM calls, all blocking the async loop.

**Fix:** Run the synthesizer in `run_in_executor`, or use `aiofiles` for disk operations.

---

### 12. **No HTTP Connection Pool Limits**

**Location:** `fetcher.py`, `searx_client.py`

**Problem:** Default `httpx.AsyncClient` has no explicit connection limits, which can cause port exhaustion under high concurrency.

**Fix:** Configure limits explicitly:

```python
limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
self._http_client = httpx.AsyncClient(limits=limits, ...)
```

---

### 13. **Critic Prompt Includes Growing Document Set**

**Location:** `critic.py`, `find_gaps()`

**Problem:** The prompt says `Total documents: {len(docs)}` but only shows first 20. However, the LLM doesn't know about the rest. More importantly, this is a **synchronous** call inside the hot fetch loop—every `critique_batch_size` documents stalls all fetching.

**Fix:** Move critic analysis to a background task that doesn't block the fetch loop, or run it concurrently with the next batch of fetches.

---

## Recommended Priority Roadmap

| Priority | Action                                                       | Expected Impact                                  |
| -------- | ------------------------------------------------------------ | ------------------------------------------------ |
| **P0**   | Add `asyncio.Semaphore` to fetch loop                        | Cuts fetch time by 5–10x                         |
| **P0**   | Run all LLM calls via `run_in_executor` or use async clients | Prevents event loop blocking                     |
| **P0**   | Fix string concatenation in `llm_client.py`                  | Reduces LLM response assembly from O(n²) to O(n) |
| **P1**   | Batch indexer LLM calls (5–10 docs/call)                     | Cuts indexer time by 5–10x                       |
| **P1**   | Remove redundant HTML parsing in extractor                   | Cuts extraction CPU by ~60%                      |
| **P1**   | Cap search concurrency                                       | Prevents SearxNG overload                        |
| **P2**   | Use `aiofiles` + `run_in_executor` for synthesizer           | Keeps async loop responsive                      |
| **P2**   | Add connection limits to HTTP clients                        | Stability under load                             |
| **P2**   | Use faster dedup hashing                                     | Minor CPU savings                                |

Would you like me to implement any of these fixes?



Let me break down **Point 11** in detail by first re-examining the relevant code paths.

## The Problem

Look at how `build_report()` is invoked:

**`deep_search.py` (async function):**

```python
result = synthesizer.synthesize(query, docs)  # <-- This is a SYNC call inside an async function
```

**`synthesizer.py`:**

```python
def synthesize(self, topic: str, docs: list[dict]) -> str:
    indexer = Indexer(self.llm, self.config)
    topics_json = indexer.process_docs(docs, topic)  # SYNC LLM calls + disk I/O

    ob = OverviewBuilder(self.llm, self.config)
    ob.build_overview(self.config.indexes_dir)  # SYNC recursive LLM calls + disk I/O

    rb = ReportBuilder(self.llm, self.config)
    report = rb.build_report(topics_json)  # SYNC recursive file reading + LLM calls
    return report
```

**`report_builder.py` — the synchronous blocking operations:**

```python
def build_report(self, topics_json: dict) -> str:
    # 1. Blocking disk read
    scratch_pad = scratch_pad_path.read_text(encoding="utf-8")

    # 2. Recursive traversal that blocks on every node
    rolling_summary = self._traverse_topics(topics_json, [], report_file, scratch_pad, rolling_summary)
    ...

def _traverse_topics(self, ...):
    for topic, subtopics in topics_dict.items():
        # 3. Multiple blocking disk reads PER topic node
        if (node_dir / "overview.md").exists():
            local_context = (node_dir / "overview.md").read_text(encoding="utf-8")
        elif (node_dir / "information.md").exists():
            local_context = (node_dir / "information.md").read_text(encoding="utf-8")

        # 4. Blocking synchronous LLM call
        if self.accumulator_tokens >= threshold:
            rolling_summary = self._flush_accumulator(...)
    ...
```

### Why This Matters in Async Code

`deep_search()` is an `async` function. The entire runtime is managed by a single **event loop**. When execution hits `synthesizer.synthesize()`, Python doesn't yield control back to the loop. It **blocks the event loop** while:

1. Reading potentially **hundreds** of `.md` files from disk sequentially
2. Sending **multiple** blocking HTTP requests to the LLM API (inside `_flush_accumulator`)
3. Accumulating all report text in memory

During this entire phase:

- No background tasks can run
- Progress callbacks are frozen
- Timeouts can't be enforced properly
- The program appears "stuck" during synthesis

## The Exact Solutions

You have **three** options, from simplest to most robust:

### Option A: Offload the Entire Synthesizer to a Thread Pool (Recommended)

Since `synthesize()` is fundamentally synchronous work, run it in a separate thread so the event loop stays free:

```python
# In deep_search.py

# BEFORE (blocking):
result = synthesizer.synthesize(query, docs)

# AFTER (non-blocking):
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, synthesizer.synthesize, query, docs)
```

This is the **minimum viable fix**. The event loop remains responsive, progress callbacks work, and the program can handle cancellation properly.

### Option B: Make File Operations Truly Async with `aiofiles`

If you want file I/O to be cooperative (yield to other tasks during disk waits):

```python
# Install: pip install aiofiles

import aiofiles

class ReportBuilder:
    async def build_report(self, topics_json: dict) -> str:
        # Async file read
        async with aiofiles.open(scratch_pad_path, "r", encoding="utf-8") as f:
            scratch_pad = await f.read()

        rolling_summary = await self._traverse_topics(...)
        return ...

    async def _traverse_topics(self, ...):
        ...
        if (node_dir / "overview.md").exists():
            async with aiofiles.open(node_dir / "overview.md", "r", encoding="utf-8") as f:
                local_context = await f.read()
```

**Caveat:** You'd still need to wrap the LLM calls (`self.llm.generate()`) in `run_in_executor` because the `LLMClient` uses synchronous `anthropic`/`openai` SDKs. So you'd end up mixing `await aiofiles...` with `await loop.run_in_executor(...)` for LLM calls.

### Option C: Full Async Architecture (Most Work, Best Result)

Restructure so the entire pipeline is async-native:

```python
class AsyncSynthesizer:
    async def synthesize(self, topic: str, docs: list[dict]) -> str:
        # Use async file operations
        # Use async LLM client (anthropic.AsyncAnthropic / openai.AsyncOpenAI)
        # Everything yields control properly
```

This requires rewriting `LLMClient` to use `AsyncAnthropic` and `AsyncOpenAI`, and updating all synthesizer methods to be `async`.

---

## Summary Table

| Approach                              | Code Change                           | Effect on Event Loop | Effort |
| ------------------------------------- | ------------------------------------- | -------------------- | ------ |
| **A** — `run_in_executor`             | 1 line in `deep_search.py`            | ✅ Freed immediately  | Low    |
| **B** — `aiofiles` + executor for LLM | Multiple lines in `report_builder.py` | ✅ Freed during I/O   | Medium |
| **C** — Full async rewrite            | Rewrite `LLMClient` + synthesizers    | ✅ Fully cooperative  | High   |

**My recommendation:** Start with **Option A** (one-line fix). It gives you 90% of the benefit immediately. If you later want true async file I/O, layer **Option B** on top.
