"""Docling document parser — PDF, DOCX, PPTX, HTML ingestion."""
from __future__ import annotations
from pathlib import Path
from omega_researcher.schemas import IngestedDocument, DocumentSource

SUPPORTED_FORMATS = {
    ".pdf", ".docx", ".pptx", ".html", ".htm",
}


class DoclingParser:
    """Parse PDF, DOCX, PPTX, HTML files into IngestedDocument using Docling."""

    def __init__(self, config):
        self.config = config
        self._converter = None  # Lazy init — docling is heavy

    def _get_converter(self):
        """Lazy-initialize Docling converter on first use."""
        if self._converter is not None:
            return self._converter

        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pipeline_opts = PdfPipelineOptions()
        pipeline_opts.do_ocr = self.config.docling_ocr
        pipeline_opts.table_structure_options.mode = self.config.docling_table_mode

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
            }
        )
        return self._converter

    def parse(self, file_path: str | Path) -> IngestedDocument:
        """Parse a single file into an IngestedDocument."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}. Supported: {SUPPORTED_FORMATS}")

        # Size check
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(f"File too large: {size_mb:.1f}MB > {self.config.max_file_size_mb}MB")

        converter = self._get_converter()
        result = converter.convert(str(path))
        doc = result.document

        # Export to markdown
        markdown_text = doc.export_to_markdown()

        # Extract tables as structured dicts
        tables = []
        for table in getattr(doc, "tables", []):
            try:
                df = table.export_to_dataframe()
                tables.append({
                    "headers": df.columns.tolist(),
                    "rows": df.values.tolist(),
                    "caption": getattr(table, "caption", ""),
                })
            except Exception:
                pass

        # Image descriptions
        images_desc = []
        for fig in getattr(doc, "pictures", []):
            try:
                caption = fig.caption_text(doc)
                if caption:
                    images_desc.append(caption)
            except Exception:
                pass

        # Metadata
        meta = getattr(doc, "metadata", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        metadata = {
            "page_count": getattr(doc, "num_pages", None),
            "author": meta.get("author", ""),
            "created": meta.get("creation_date", ""),
            "title": meta.get("title", path.stem),
            "file_format": ext,
            "file_size_mb": round(size_mb, 2),
        }

        # Chunk for indexing
        raw_chunks = _chunk_text(markdown_text, max_chars=1500)

        return IngestedDocument(
            source_type=DocumentSource.FILE,
            source_path=str(path),
            title=metadata.get("title") or path.stem,
            text=markdown_text,
            tables=tables,
            images_desc=images_desc,
            metadata=metadata,
            raw_chunks=raw_chunks,
        )

    def parse_batch(self, paths: list[str | Path]) -> list[IngestedDocument]:
        """Parse multiple files, skipping failures with warnings."""
        results = []
        for p in paths:
            try:
                results.append(self.parse(p))
                print(f"[docling] OK: {p}")
            except Exception as e:
                print(f"[docling] FAIL: {p}: {e}")
        return results


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text on double-newline boundaries, respecting max_chars."""
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks
