Now I have a clear picture of both the generated reports and the internal pipeline data. Here is the comprehensive quality improvement plan.

---

## Report Quality Assessment

### Photosynthesis Report — Strengths

- Scientifically accurate for a biology textbook-level overview
- Well-structured topic hierarchy (9 main topics, ~30 subtopics)
- Good depth on C3/C4/CAM pathways

### Photosynthesis Report — Weaknesses

**1. Massive Content Redundancy** (~30% duplicated):

```
"Importance" covered in 3 places:
  → Photosynthesis Overview / Importance
  → Separate "Importance of Photosynthesis" section  
  → Global Carbon Cycle / Oxygen Production subsections

"Photorespiration" covered in 4 places:
  → Standalone section
  → Inside C3 Photosynthesis
  → Inside CAM Photosynthesis
  → Inside Historical Perspectives & Optimization

"Light-Dependent Reactions" repeated twice:
  → Under Photosynthetic Structures / Thylakoids
  → As full separate "# Light-Dependent Reactions" section
```

**2. LLM Hallucination** — The "Nobel Prize Recognition" section says the prize was awarded "in 1988" but never names who won or what exactly for. The LLM is being vague because it's unsure.

**3. No Inline Citations** — Despite the indexer writing source headers into `information.md` files, zero citations survive into the final report.

**4. Overlapping Topic Hierarchy** — The indexer created separate parallel trees for the same thing:

```
Light Reactions: { Chlorophyll, Electron Transport, Water Splitting, ATP }
Photosynthetic Pigments: { Chlorophyll A, Accessory, Photoprotection }
Photosynthetic Structures: { Chloroplast, Thylakoids, Stroma }
```

These should be one coherent branch: `Structures → Light Reactions → Pigments → Electron Transport`.

---

### Billionaire Report — Severe Quality Issues

- **Extreme repetition**: `$252.3B`, `78% adoption`, `Stanford Snyder Lab 300%`, same statistics in **every single section**
- **Fabricated references**: "Stanford Snyder Lab of Genetics", "Harvard Business Review studies: networks accelerate 3-5x" — likely LLM hallucinations
- **Buzzword density > signal density**: Each section is 80% filler, 20% actual content
- **No actionable specifics**: "Build proprietary systems", "Develop deep integration" — zero concrete steps
- **Vagueness masquerading as depth**: "The Zero to Billionaire Framework treats physical wellness as the first operational leverage point" — meaningless jargon

---

## Root Causes in the Pipeline

### Cause 1: Indexer Has No Semantic Deduplication

**Current behavior:** The Indexer sends batch 1 → LLM proposes topics like `{Light Reactions: {...}}`. Batch 2 → LLM sees the growing hierarchy but with only JSON keys as context, so it proposes `{Photosynthetic Pigments: {...}}` — a separate parallel tree for the same domain.

```python
# indexer.py — the prompt includes:
## Current Topics Hierarchy
{"Light Reactions": {"Chlorophyll Pigments": {}, ...}}
# ...LLM gets batch 2 about pigments and creates:
"updated_topics_hierarchy": {
  "Light Reactions": {...},
  "Photosynthetic Pigments": {"Chlorophyll A": {}, ...}  # Duplicate domain!
}
```

**Fix:** Add a dedup step to the indexer's system prompt:

```
Before adding NEW topics, check if they belong under existing topics.
If a document covers "Chlorophyll A", place it under "Light Reactions / Chlorophyll Pigments"
rather than creating a new top-level topic.
```

Or, post-process the hierarchy with an embedding similarity check to merge overlapping branches.

### Cause 2: Report Builder Loses Citations

**Current behavior:** The indexer writes source headers to `information.md`:

```markdown
### Source: [Light-Dependent Reactions](https://...)
### Source: [Photosynthesis](https://...)

...extracted content...
```

But the OverviewBuilder and ReportBuilder **never instruct the LLM to preserve citations**. The LLM paraphrases everything, stripping all attribution.

**Fix:** Add citation preservation to the ReportBuilder's system prompt:

```
When writing sections, preserve source citations inline.
Use the format: [Source Title](URL) after each key claim.
Example: "Photosynthesis occurs in chloroplasts [Nature Scitable](https://...)"
```

### Cause 3: Rolling Summary Is Too Weak to Prevent Duplication

**Current behavior:** The rolling summary is a 1-paragraph blurb updated after each flush:

```python
rolling_summary = "This report is just starting."  # Initial
# After flush 1: updated by LLM to a short paragraph
# After flush 2: updated again
```

But the ReportBuilder generates sections for **multiple accumulated topics in one LLM call**, and the LLM has no structured way to check what was already written in prior sections. It only sees the rolling summary text.

**Fix:** Instead of a free-text rolling summary, maintain a **set of already-covered claims**:

```python
self.covered_claims: set[str] = set()

def _flush_accumulator(self, ...):
    prompt = f"""
    ## Previously Covered Topics (DO NOT repeat):
    {', '.join(self.covered_topics)}

    ## Previously Stated Claims (DO NOT repeat):
    {', '.join(list(self.covered_claims)[:50])}

    ## New Topics to Cover:
    {combined_context}
    """
    # After LLM response, extract new claims and add to covered_claims
```

### Cause 4: No Quality Feedback Loop

The **Critic** only runs during document collection to find research gaps. There is **no post-synthesis critic** that reviews the final report for:

- Redundancy
- Factual accuracy
- Missing key details

**Fix:** Add a final `ReportCritic` step after synthesis:

```python
# After synthesizer.synthesize()
report_review = await loop.run_in_executor(
    None, report_critic.review, query, result
)
if report_review.needs_revision:
    result = report_critic.revise(result, report_review.suggestions)
```

### Cause 5: Indexer `text[:10000]` Truncation Loses Information

**Current behavior:**

```python
text = doc.get("text", "")[:10000]  # Hard truncation
```

This throws away 90%+ of long documents. If a document has 50KB of text, the indexer only sees the first 10K characters of each doc in a batch.

**Fix:** Use a sliding-window approach or a smarter summarization:

```python
# Option A: Take first + middle + last
text_len = len(text)
text = text[:4000] + "\n...[middle]...\n" + text[text_len//2-1000:text_len//2+1000] + "\n...[end]...\n" + text[-4000:]

# Option B: Pre-summarize long docs with a cheap call before indexing
```

---

## Implementation Plan

| Priority | Improvement                                     | Where                                     | Impact                                        |
| -------- | ----------------------------------------------- | ----------------------------------------- | --------------------------------------------- |
| **P0**   | Citation preservation in ReportBuilder          | `report_builder.py` system prompt         | Adds credibility, prevents hallucination look |
| **P0**   | Topic dedup in Indexer system prompt            | `indexer.py` system prompt                | Cuts redundancy ~30%                          |
| **P1**   | Replace rolling summary with covered-claims set | `report_builder.py` `_flush_accumulator`  | Prevents repeated statements                  |
| **P1**   | Post-synthesis ReportCritic                     | New `report_critic.py` + `deep_search.py` | Catches redundancy + facts                    |
| **P2**   | Smarter document truncation                     | `indexer.py` `_build_prompt`              | Better coverage of long docs                  |
| **P2**   | Remove `async def` from `progress_callback`     | `caller.py`                               | Already broken, fix it                        |

---

## Specific Prompt Fix for Dedup (Highest Leverage)

The indexer system prompt currently has no dedup instruction. Adding these lines would immediately improve topic organization:

```
4. DEDUPLICATION: Before adding a new topic, scan existing topics and 
   check if it logically belongs under one of them. For example:
   - "Chlorophyll A" belongs under "Light Reactions" → "Pigments"
   - "Oxygen Production" belongs under "Importance" or "Light Reactions"
   - Do NOT create parallel top-level topics for concepts that fit under 
     an existing branch.
   - Prefer nesting under the most specific relevant parent.
```

Similarly for the ReportBuilder:

```
Before writing each section, check the rolling summary to ensure you are 
NOT repeating claims already made. If a topic was already covered in detail 
in a previous section, briefly reference it with a cross-reference rather 
than re-explaining it.
```

---

Would you like me to proceed with implementing these quality improvements?
