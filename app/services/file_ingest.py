import io
import logging
from typing import Any, BinaryIO, Tuple, Union
import pandas as pd
from app.config import settings

logger = logging.getLogger(__name__)


class FileIngestionService:
    """Service for streaming and validating CSV/XLSX file ingestion."""

    def ingest_file(
        self,
        file_input: Union[str, BinaryIO, bytes],
        filename: str,
        text_column: str,
        max_rows: int = settings.MAX_UPLOAD_ROWS,
        chunk_size: int = 10000,
    ) -> Tuple[pd.DataFrame, dict[str, int]]:
        """Ingest, validate, and normalize a CSV or Excel file.

        Rows with missing or empty category text are preserved and assigned 'Unclassified'
        so they can be grouped into the 'Others' category downstream without data loss.

        Args:
            file_input: File path, binary file-like object, or raw bytes.
            filename: Original filename to determine file extension.
            text_column: Column name containing the category text.
            max_rows: Maximum allowed rows limit.
            chunk_size: Chunk size for streaming CSV read.

        Returns:
            Tuple of (processed DataFrame, stats dictionary).
        """
        ext = filename.lower().split(".")[-1]

        if ext in ("csv", "txt"):
            df = self._read_csv_streaming(
                file_input, text_column, max_rows, chunk_size
            )
        elif ext in ("xlsx", "xls"):
            df = self._read_excel(file_input, text_column, max_rows)
        else:
            raise ValueError(
                f"Unsupported file format: '.{ext}'. Only CSV and XLSX files are supported."
            )

        if text_column not in df.columns:
            raise ValueError(
                f"Column '{text_column}' not found in file. Available columns: {list(df.columns)}"
            )

        total_rows = len(df)
        if total_rows > max_rows:
            raise ValueError(
                f"Row count ({total_rows}) exceeds maximum allowed limit of {max_rows} rows."
            )

        df_processed = df.copy()

        # Identify empty / NaN / whitespace rows in text_column
        raw_text = df_processed[text_column].astype(str)
        is_empty = (
            df_processed[text_column].isna()
            | (raw_text.str.strip() == "")
            | (raw_text.str.strip().str.lower() == "nan")
            | (raw_text.str.strip().str.lower() == "none")
            | (raw_text.str.strip().str.lower() == "null")
        )

        empty_category_count = int(is_empty.sum())

        # Normalize text: trim whitespace and collapse multiple spaces; replace empty with 'Unclassified'
        normalized = (
            raw_text.str.strip().str.replace(r"\s+", " ", regex=True)
        )
        normalized[is_empty] = "Unclassified"
        df_processed["normalized_text"] = normalized

        # Assign 1-indexed row_id
        df_processed["row_id"] = range(1, total_rows + 1)

        logger.info(
            f"Ingestion stats - Total rows: {total_rows}, Empty/Unclassified category rows: {empty_category_count}"
        )

        stats = {
            "total_rows": total_rows,
            "dropped_rows": 0,
            "valid_rows": total_rows,
            "empty_category_count": empty_category_count,
        }

        return df_processed, stats

    def _read_csv_streaming(
        self,
        file_input: Union[str, BinaryIO, bytes],
        text_column: str,
        max_rows: int,
        chunk_size: int,
    ) -> pd.DataFrame:
        """Stream read CSV with encoding fallback (utf-8 -> latin-1)."""
        buffer = self._to_buffer_or_path(file_input)

        for encoding in ("utf-8", "latin-1"):
            try:
                if isinstance(buffer, io.BytesIO):
                    buffer.seek(0)

                chunks = []
                accumulated_rows = 0

                for chunk in pd.read_csv(
                    buffer, chunksize=chunk_size, encoding=encoding
                ):
                    accumulated_rows += len(chunk)
                    if accumulated_rows > max_rows:
                        raise ValueError(
                            f"File exceeds maximum allowed limit of {max_rows} rows."
                        )
                    chunks.append(chunk)

                if not chunks:
                    return pd.DataFrame()
                return pd.concat(chunks, ignore_index=True)
            except (UnicodeDecodeError, UnicodeError):
                if encoding == "latin-1":
                    raise
                logger.warning("UTF-8 decoding failed, falling back to latin-1")
            except ValueError as ve:
                raise ve

        raise ValueError("Failed to parse CSV file with supported encodings.")

    def _read_excel(
        self,
        file_input: Union[str, BinaryIO, bytes],
        text_column: str,
        max_rows: int,
    ) -> pd.DataFrame:
        """Read Excel file into DataFrame."""
        buffer = self._to_buffer_or_path(file_input)
        df = pd.read_excel(buffer)
        if len(df) > max_rows:
            raise ValueError(
                f"File exceeds maximum allowed limit of {max_rows} rows."
            )
        return df

    @staticmethod
    def _to_buffer_or_path(
        file_input: Union[str, BinaryIO, bytes]
    ) -> Union[str, io.BytesIO]:
        """Convert input to a file path or BytesIO buffer."""
        if isinstance(file_input, bytes):
            return io.BytesIO(file_input)
        elif isinstance(file_input, str):
            return file_input
        elif hasattr(file_input, "read"):
            content = file_input.read()
            return io.BytesIO(content)
        else:
            raise ValueError("Invalid file input type.")


file_ingestion_service = FileIngestionService()
