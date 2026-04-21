"""Data tools — pandas analytics exposed as MCP-callable functions."""
from __future__ import annotations
from omega_researcher.ingestion.data_reader import DataReader
from omega_researcher.config import Config


class DataTools:
    def __init__(self, config: Config):
        self.reader = DataReader(config)

    def head(self, file_path: str, n: int = 10) -> str:
        try:
            return self.reader.head(file_path, n)
        except Exception as e:
            return f"[data_head error] {e}"

    def summary(self, file_path: str) -> str:
        try:
            return self.reader.summary(file_path)
        except Exception as e:
            return f"[data_summary error] {e}"

    def schema(self, file_path: str) -> str:
        try:
            return self.reader.schema(file_path)
        except Exception as e:
            return f"[data_schema error] {e}"

    def query(self, file_path: str, pandas_query: str) -> str:
        try:
            return self.reader.query(file_path, pandas_query)
        except Exception as e:
            return f"[data_query error] {e}"
