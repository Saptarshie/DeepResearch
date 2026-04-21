"""File ingestion tools — Docling + DataReader via MCP."""
from __future__ import annotations
from pathlib import Path
from omega_researcher.config import Config
from omega_researcher.ingestion.docling_parser import DoclingParser, SUPPORTED_FORMATS
from omega_researcher.ingestion.data_reader import DataReader, CSV_EXTS, EXCEL_EXTS


class FileTools:
    def __init__(self, config: Config, llm=None, index_manager=None):
        self.config = config
        self.llm = llm
        self.index_manager = index_manager
        self._docling = None
        self._data_reader = DataReader(config)

    def _get_docling(self):
        if self._docling is None:
            self._docling = DoclingParser(self.config)
        return self._docling

    def ingest(self, file_path: str) -> str:
        """Parse a document file (PDF/DOCX/PPTX/HTML) and return markdown text."""
        try:
            doc = self._get_docling().parse(file_path)
            # Optionally index immediately
            if self.index_manager and self.llm:
                self.index_manager.index_document(doc, file_path, self.llm)
            return doc.text[:8000]  # Return preview
        except Exception as e:
            return f"[ingest_document error] {e}"

    def ingest_data(self, file_path: str) -> str:
        """Load a CSV/Excel file and return schema + preview."""
        try:
            schema = self._data_reader.schema(file_path)
            head = self._data_reader.head(file_path, 5)
            return f"{schema}\n\n## Preview (first 5 rows)\n{head}"
        except Exception as e:
            return f"[ingest_data_file error] {e}"
