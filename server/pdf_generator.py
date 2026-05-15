from __future__ import annotations

import asyncio
import logging
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


# Minimal markdown-to-HTML converter (headings, lists, code, quotes, tables)
def _md_to_html(md: str) -> str:
    import re

    html = md

    # ── Extract Mermaid blocks FIRST (before any HTML escaping) ──
    mermaid_blocks: list[str] = []

    def _mermaid_extract(m: re.Match) -> str:
        mermaid_blocks.append(m.group(1))
        return f"\n\n___MERMAID_{len(mermaid_blocks) - 1}___\n\n"

    html = re.sub(
        r"```mermaid\n(.*?)```",
        _mermaid_extract,
        html,
        flags=re.DOTALL,
    )

    # Escape HTML entities (only for non-Mermaid content)
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Fenced code blocks (non-mermaid)
    html = re.sub(
        r"```(\w+)?\n(.*?)```",
        lambda m: f'<pre><code class="language-{m.group(1) or "text"}">{m.group(2)}</code></pre>',
        html,
        flags=re.DOTALL,
    )

    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Headings
    for level in range(6, 0, -1):
        html = re.sub(
            rf"^{ '#' * level } (.+)$",
            rf"<h{level}>\1</h{level}>",
            html,
            flags=re.MULTILINE,
        )

    # Bold / italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    html = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html)

    # Blockquotes
    html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)

    # Tables (simple)
    def _table_repl(m: re.Match) -> str:
        lines = m.group(0).strip().split("\n")
        rows = []
        for i, line in enumerate(lines):
            if i == 1 and set(line.strip()) <= {"|", "-", " ", ":"}:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        return "<table>" + "".join(rows) + "</table>"

    html = re.sub(
        r"(\|[^\n]+\|\n)+(\|[-:\|\s]+\|\n)(\|[^\n]+\|\n?)+",
        _table_repl,
        html,
    )

    # Horizontal rules
    html = re.sub(r"^---+$", "<hr>", html, flags=re.MULTILINE)

    # Lists
    html = re.sub(r"^\* (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^(<li>.+</li>\n?)+", r"<ul>\g<0></ul>", html, flags=re.MULTILINE)

    # Paragraphs
    paragraphs = html.split("\n\n")
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("<"):
            wrapped.append(p)
        else:
            wrapped.append(f"<p>{p}</p>")
    html = "\n".join(wrapped)

    # Restore Mermaid blocks as divs
    for i, block in enumerate(mermaid_blocks):
        placeholder = f"<p>___MERMAID_{i}___</p>"
        html = html.replace(
            placeholder,
            f'<div class="mermaid">{block}</div>',
        )

    return html


def _build_html_doc(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  @page {{ size: A4; margin: 20mm; }}
  body {{
    font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
    max-width: 170mm;
    margin: 0 auto;
  }}
  h1 {{ font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 4pt; }}
  h2 {{ font-size: 16pt; border-bottom: 1px solid #ccc; padding-bottom: 3pt; margin-top: 18pt; }}
  h3 {{ font-size: 13pt; margin-top: 14pt; }}
  code {{ background: #f4f4f4; padding: 1pt 3pt; border-radius: 3pt; font-size: 10pt; }}
  pre {{ background: #f4f4f4; padding: 8pt; border-radius: 4pt; overflow-x: auto; }}
  blockquote {{ border-left: 3pt solid #666; margin-left: 0; padding-left: 10pt; color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10pt 0; }}
  th, td {{ border: 1pt solid #ccc; padding: 4pt 6pt; text-align: left; }}
  th {{ background: #f0f0f0; }}
  hr {{ border: none; border-top: 1pt solid #ccc; margin: 14pt 0; }}
  .mermaid {{ text-align: center; margin: 10pt 0; }}
</style>
</head>
<body>
{body_html}
<script>
  mermaid.initialize({{startOnLoad: false, theme: 'default'}});
  // Run mermaid explicitly after DOM is ready
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', function() {{
      mermaid.run();
    }});
  }} else {{
    mermaid.run();
  }}
</script>
</body>
</html>"""


def _generate_pdf_sync(markdown_content: str, output_path: str) -> None:
    """Sync PDF generation — safe to run inside run_in_executor."""
    from playwright.sync_api import sync_playwright

    body_html = _md_to_html(markdown_content)
    html_doc = _build_html_doc(body_html)

    # Use data URL so page.goto triggers proper load events
    data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html_doc)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Navigate to data URL — fires load event properly
        page.goto(data_url, wait_until="networkidle")

        # Wait for Mermaid CDN script to actually load
        try:
            page.wait_for_function(
                "() => typeof mermaid !== 'undefined'",
                timeout=10000,
            )
            logger.info("Mermaid library loaded from CDN")
        except Exception:
            logger.warning("Mermaid library failed to load from CDN")
            # Still generate PDF, just without diagrams
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"},
            )
            browser.close()
            logger.info("PDF generated (no Mermaid): %s", output_path)
            return

        # Check if there are mermaid blocks to render
        mermaid_blocks = page.locator(".mermaid").count()
        if mermaid_blocks == 0:
            logger.info("No Mermaid blocks found in document")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"},
            )
            browser.close()
            logger.info("PDF generated: %s", output_path)
            return

        # Explicitly trigger Mermaid rendering
        try:
            # mermaid.run() returns a Promise; evaluate resolves it automatically
            page.evaluate("""
                () => mermaid.run({ querySelector: '.mermaid' })
            """)
            logger.info("Mermaid run() executed for %s blocks", mermaid_blocks)
        except Exception as exc:
            logger.warning("Mermaid run() failed: %s", exc)

        # Wait for SVGs to appear (poll for up to 20s)
        try:
            page.wait_for_selector(".mermaid svg", timeout=20000)
            rendered = page.locator(".mermaid svg").count()
            logger.info("Mermaid rendered %s/%s diagram(s)", rendered, mermaid_blocks)
        except Exception:
            logger.warning(
                "Mermaid SVG render timeout (%s blocks), proceeding anyway",
                mermaid_blocks,
            )

        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"},
        )
        browser.close()
    logger.info("PDF generated: %s", output_path)


async def generate_pdf(markdown_content: str, output_path: str) -> None:
    """Render markdown with Mermaid diagrams to PDF via Playwright."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _generate_pdf_sync, markdown_content, output_path)
