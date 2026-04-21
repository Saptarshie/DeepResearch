"""Data reader — CSV/Excel ingestion with pandas analytics API."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from omega_researcher.schemas import IngestedDocument, DocumentSource

EXCEL_EXTS = {".xlsx", ".xlsm", ".xls", ".ods"}
CSV_EXTS = {".csv", ".tsv"}


class DataReader:
    """
    Reads structured tabular files into IngestedDocument.
    Also exposes head(), summary(), schema() for MCP tools.
    """

    def __init__(self, config):
        self.config = config
        self._loaded: dict[str, Any] = {}  # cache: path -> df

    def load(self, file_path: str | Path) -> Any:
        """Load file into a pandas DataFrame (cached)."""
        import pandas as pd

        path = Path(file_path)
        key = str(path.resolve())
        if key not in self._loaded:
            ext = path.suffix.lower()
            if ext in CSV_EXTS:
                sep = "\t" if ext == ".tsv" else ","
                self._loaded[key] = pd.read_csv(path, sep=sep)
            elif ext in EXCEL_EXTS:
                engine = "xlrd" if ext == ".xls" else (
                    "odf" if ext == ".ods" else "openpyxl"
                )
                self._loaded[key] = pd.read_excel(path, engine=engine)
            else:
                raise ValueError(f"Unsupported data format: {ext}")
        return self._loaded[key]

    def head(self, file_path: str, n: int = 5) -> str:
        """Return first N rows as markdown table."""
        df = self.load(file_path)
        return df.head(n).to_markdown(index=False)

    def summary(self, file_path: str) -> str:
        """Return df.describe() + dtypes as markdown."""
        df = self.load(file_path)
        desc = df.describe(include="all").to_markdown()
        dtype = df.dtypes.to_frame("dtype").to_markdown()
        return f"### Shape\n{df.shape}\n\n### dtypes\n{dtype}\n\n### describe()\n{desc}"

    def schema(self, file_path: str) -> str:
        """Return column names, dtypes, null counts."""
        df = self.load(file_path)
        info = []
        for col in df.columns:
            null_count = df[col].isna().sum()
            info.append(f"- `{col}` ({df[col].dtype}) -- {null_count} nulls")
        return "### Schema\n" + "\n".join(info)

    def query(self, file_path: str, pandas_query: str) -> str:
        """Run a pandas .query() expression and return result as markdown."""
        df = self.load(file_path)
        try:
            result = df.query(pandas_query)
            return result.head(50).to_markdown(index=False)
        except Exception as e:
            return f"[query error] {e}"

    def to_ingested_document(self, file_path: str | Path) -> IngestedDocument:
        """Convert to unified IngestedDocument for indexer."""
        import pandas as pd

        path = Path(file_path)
        df = self.load(str(path))

        # For multi-sheet Excel
        sheets_text = ""
        if path.suffix.lower() in EXCEL_EXTS:
            try:
                xl = pd.ExcelFile(path)
                for sheet in xl.sheet_names:
                    sdf = pd.read_excel(path, sheet_name=sheet)
                    sheets_text += f"\n\n## Sheet: {sheet}\n{sdf.head(50).to_markdown()}"
            except Exception:
                pass

        text = (
            self.summary(str(path))
            + "\n\n## Preview\n"
            + self.head(str(path), 20)
            + sheets_text
        )

        return IngestedDocument(
            source_type=DocumentSource.DATA,
            source_path=str(path),
            title=path.stem,
            text=text,
            tables=[{"headers": df.columns.tolist(), "rows": df.head(100).values.tolist()}],
            images_desc=[],
            metadata={
                "rows": len(df),
                "columns": len(df.columns),
                "dtypes": df.dtypes.astype(str).to_dict(),
                "file_format": path.suffix.lower(),
            },
            raw_chunks=[text],
        )
