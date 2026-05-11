Based on the code you provided in `report_builder.py` and `indexer.py`, I can pinpoint exactly what is causing the "Frankenstein" copy-paste loop and the repeated section headers in your v2 report.

It is a classic race condition between your **Accumulator logic**, your **Topic Traversal loop**, and conflicting **Prompt Instructions**.

Here are the three root causes generating this bug:

### 1. The Accumulator Boundary Fragmentation (`report_builder.py`)

This is the primary culprit for the exact same header repeating sequentially.

Look at how you process the topics in `_traverse_topics`:

```python
if self.accumulator_tokens >= threshold:
    rolling_summary = self._flush_accumulator(report_file, scratch_pad, rolling_summary, emit)

```

Your accumulator flushes whenever it hits `min_accumulator_threshold` (defaulting to 400).
Now imagine a large parent topic called `Towards End-to-End AI Coding Harness Integration` that contains 6 subtopics.

- The system processes Subtopics 1 and 2. The token count hits 400. **Flush 1 triggers.**
- The LLM looks at the path `["Towards End-to-End...", "Subtopic 1"]` and is explicitly told by your prompt to: _"Use markdown headings exactly matching the topic hierarchy given."_ So, it generates the parent header `## Towards End-to-End...` followed by the subtopics.
- The loop continues to Subtopics 3 and 4. The token count hits 400 again. **Flush 2 triggers.**
- The LLM gets the new paths `["Towards End-to-End...", "Subtopic 3"]`. It blindly follows the structure rule again and generates the parent header `## Towards End-to-End...` a **second time**, followed by the new subtopics.

Because the accumulator flushes _mid-way_ through a parent node's children, the LLM is repeatedly re-introducing the parent topic as if it's brand new.

### 2. Conflicting Prompt Directives (`report_builder.py`)

Your system prompt contains two rules that are fighting each other to the death:

1. **The Structure Rule:** _"Use markdown headings exactly matching the topic hierarchy given."_
2. **The Anti-Deduplication Rule:** _"If the rolling summary already covers the topic, write a brief cross-reference instead of repeating..."_

When Flush 2 happens (from the scenario above), the LLM reads the rolling summary and sees that `Towards End-to-End...` was already written. It wants to follow the Anti-Deduplication rule, but it _also_ has to output the new subtopic content and follow the Structure rule.
The LLM compromises: It outputs the exact same top-level header again to satisfy the Structure rule, but slightly varies the introductory text to satisfy the Anti-Deduplication rule. This creates the disjointed, repetitive narrative loop you observed.

### 3. The Indexer "JSON Overwrite" Weakness (`indexer.py`)

In `indexer.py`, you process documents in batches and ask the LLM to merge them into the global JSON hierarchy:

```python
if "updated_topics_hierarchy" in response:
    topics_json = response["updated_topics_hierarchy"]

```

While your prompt explicitly demands _"AGGRESSIVE TOPIC DEDUPLICATION"_, LLMs are notoriously bad at deeply merging JSON objects contextually over multiple sliding windows.
If Batch 1 contains information about "End-to-End Pipelines" and Batch 4 contains "Towards End-to-End Integration", the LLM will often just append a new top-level node rather than merging the content into the existing node from Batch 1. This results in the Report Builder eventually processing two almost identical top-level nodes hours apart.

### How to Fix It

To achieve the Gold Standard v4, you need to fix the chunking boundary.
**Do not flush the accumulator strictly by token count if you are in the middle of a parent node's children.** Instead, modify `_traverse_topics` to only allow a flush _after_ it has finished iterating through all the subtopics of a specific parent (i.e., flush at the boundaries of top-level or secondary-level nodes), even if it goes slightly over the token threshold.

Alternatively, modify the `ReportBuilder` prompt to explicitly state: _"If the current topic paths share a parent with the Rolling Summary, DO NOT output the parent heading again. Output ONLY the subtopic headings."_
