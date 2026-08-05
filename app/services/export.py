import csv
import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Tuple
import pandas as pd
from app.config import settings

logger = logging.getLogger(__name__)


class ExportService:
    """Service for streaming per-group CSV exports and packaging manifest + ZIP archives."""

    def export_groups_to_zip(
        self,
        df: pd.DataFrame,
        job_id: str,
        total_unique_categories: int,
        output_dir: str = settings.JOB_STORAGE_PATH,
    ) -> Tuple[str, Dict[str, Any]]:
        """Stream export group CSV files, create manifest.json, and package into a ZIP.

        Args:
            df: Mapped DataFrame containing 'group_name' column.
            job_id: Job identifier.
            total_unique_categories: Count of unique category strings before clustering.
            output_dir: Base directory for storing output zip archives.

        Returns:
            Tuple of (zip_file_path, export_stats dict).
        """
        os.makedirs(output_dir, exist_ok=True)
        zip_file_path = os.path.join(output_dir, f"job_{job_id}_export.zip")
        temp_dir = tempfile.mkdtemp(prefix=f"export_{job_id}_")

        try:
            total_input_rows = len(df)
            grouped = df.groupby("group_name", sort=False)
            final_group_count = len(grouped)

            group_manifest_items: List[Dict[str, Any]] = []
            used_filenames: set[str] = set()
            exported_row_counter = 0

            # Stream export each group to a CSV file
            for group_name, group_df in grouped:
                group_row_count = len(group_df)
                sanitized_name = self._sanitize_filename(str(group_name))
                filename = self._dedupe_filename(sanitized_name, used_filenames)
                file_path = os.path.join(temp_dir, filename)

                # Export CSV using required formatting options
                group_df.to_csv(
                    file_path,
                    index=False,
                    encoding="utf-8-sig",
                    quoting=csv.QUOTE_MINIMAL,
                    lineterminator="\n",
                )

                exported_row_counter += group_row_count
                group_manifest_items.append(
                    {
                        "group_name": str(group_name),
                        "filename": filename,
                        "row_count": group_row_count,
                    }
                )

            # Strict validation: sum of exported rows must equal input row count
            if exported_row_counter != total_input_rows:
                raise ValueError(
                    f"Export row mismatch error: Exported {exported_row_counter} rows, but input DataFrame had {total_input_rows} rows."
                )

            # Build manifest.json
            taxonomy_summary = (
                f"{total_unique_categories:,} categories -> {final_group_count} groups"
            )
            manifest_content = {
                "job_id": job_id,
                "total_input_rows": total_input_rows,
                "total_exported_rows": exported_row_counter,
                "taxonomy_summary": taxonomy_summary,
                "total_unique_categories": total_unique_categories,
                "total_groups": final_group_count,
                "groups": group_manifest_items,
            }

            manifest_path = os.path.join(temp_dir, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_content, f, indent=2)

            # Package into ZIP using ZIP_DEFLATED
            with zipfile.ZipFile(
                zip_file_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, temp_dir)
                        zipf.write(full_path, arcname=arcname)

            stats = {
                "job_id": job_id,
                "zip_path": zip_file_path,
                "total_exported_rows": exported_row_counter,
                "total_groups": final_group_count,
                "taxonomy_summary": taxonomy_summary,
                "zip_file_size_bytes": os.path.getsize(zip_file_path),
            }

            logger.info(
                f"Export Complete - Job: {job_id}, ZIP: {zip_file_path}, Rows: {exported_row_counter}, Groups: {final_group_count}"
            )
            return zip_file_path, stats

        except Exception as e:
            logger.error(f"Export failed for job {job_id}: {e}")
            if os.path.exists(zip_file_path):
                try:
                    os.remove(zip_file_path)
                except Exception:
                    pass
            raise e
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string to be a safe OS filename."""
        clean = re.sub(r'[\\/*?:"<>|]', "", name)
        clean = clean.strip().replace(" ", "_").lower()
        clean = re.sub(r"_+", "_", clean)
        return clean or "group"

    @staticmethod
    def _dedupe_filename(base_name: str, used_names: set[str]) -> str:
        """Ensure unique filename by appending counter if name collision occurs."""
        candidate = f"{base_name}.csv"
        counter = 1
        while candidate in used_names:
            candidate = f"{base_name}_{counter}.csv"
            counter += 1
        used_names.add(candidate)
        return candidate


export_service = ExportService()
