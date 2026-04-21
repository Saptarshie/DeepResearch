"""Rolling summary — auto-compressing research context."""
from __future__ import annotations
from pathlib import Path


class RollingSummary:
    """
    Maintains a compressed rolling summary of research progress.
    Auto-compresses via LLM when token estimate exceeds threshold.
    """

    def __init__(self, config, llm_client=None):
        self.path = Path(config.rolling_summary_path)
        self.max_tokens = config.rolling_summary_max_tokens
        self.llm = llm_client
        self._text = self._load()

    def _load(self) -> str:
        if self.path.exists():
            return self.path.read_text(encoding="utf-8")
        return ""

    def update(self, new_info: str, context: str = "") -> None:
        """
        Append new information. If too long, compress via LLM.
        new_info: what was just learned / done
        context:  current query for relevance filtering
        """
        self._text += f"\n\n---\n{new_info}"

        # Estimate tokens (rough: 4 chars ≈ 1 token)
        if len(self._text) // 4 > self.max_tokens:
            self._compress(context)

        self._save()

    def _compress(self, context: str) -> None:
        """Compress the rolling summary using the LLM."""
        if not self.llm:
            # No LLM available — just truncate
            self._text = self._text[-(self.max_tokens * 4):]
            print("[rolling_summary] Truncated (no LLM available for compression).")
            return

        prompt = f"""The following is a rolling research summary that has grown too long.
Research query context: {context}

Compress this into a dense, information-rich summary (keep all key facts,
discoveries, contradictions, and open questions). Target ~800 tokens.

CURRENT SUMMARY:
{self._text}"""

        try:
            compressed = self.llm.generate(
                prompt,
                system="You are a lossless research summarizer. Keep all key findings.",
                max_tokens=1200,
            )
            self._text = f"[COMPRESSED SUMMARY]\n{compressed}"
            print("[rolling_summary] Compressed context via LLM.")
        except Exception as e:
            # Fallback: truncate
            self._text = self._text[-(self.max_tokens * 4):]
            print(f"[rolling_summary] Compression failed ({e}), truncated instead.")

    def get(self) -> str:
        return self._text

    def _save(self) -> None:
        self.path.write_text(self._text, encoding="utf-8")

    def reset(self) -> None:
        self._text = ""
        if self.path.exists():
            self.path.unlink()

    def __repr__(self) -> str:
        chars = len(self._text)
        return f"RollingSummary(chars={chars}, path={self.path})"
