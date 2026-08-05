import logging
import os
from typing import Any, Dict
from app.models.domain import JobStatus
from app.services.category_assignment import category_assignment_service
from app.services.clustering import clustering_service
from app.services.embedding import embedding_service
from app.services.export import export_service
from app.services.file_ingest import file_ingestion_service
from app.services.groq_service import groq_service
from app.services.job_manager import job_manager

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Orchestrates end-to-end classification job pipeline with state tracking and error handling."""

    def run_classification_job(
        self,
        job_id: str,
        file_path: str,
        category_column: str,
        cleanup_uploaded_file: bool = True,
    ) -> None:
        """Run Stages 2 through 6 in sequence, updating job status at each stage transition."""
        try:
            # Stage 2: Ingestion
            job_manager.update_status(job_id, JobStatus.INGESTING)
            filename = os.path.basename(file_path)
            df_processed, ingest_stats = file_ingestion_service.ingest_file(
                file_input=file_path,
                filename=filename,
                text_column=category_column,
            )

            # Stage 3: Embedding
            job_manager.update_status(job_id, JobStatus.EMBEDDING)
            unique_cats, row_map = embedding_service.extract_unique_categories(
                df_processed
            )
            emb_map = embedding_service.embed_categories(unique_cats)

            # Stage 4: Clustering with total row count awareness
            job_manager.update_status(job_id, JobStatus.CLUSTERING)
            total_rows = ingest_stats.get("total_rows", len(df_processed))
            cat_clusters, cluster_stats = (
                clustering_service.cluster_unique_categories(
                    category_embeddings=emb_map,
                    total_rows=total_rows,
                )
            )

            # Stage 5: Naming
            job_manager.update_status(job_id, JobStatus.NAMING)
            from collections import defaultdict

            cluster_members: Dict[int, list[str]] = defaultdict(list)
            for cat, cid in cat_clusters.items():
                cluster_members[cid].append(cat)

            named_clusters = groq_service.name_clusters(cluster_members)

            # Stage 6: Assigning
            job_manager.update_status(job_id, JobStatus.ASSIGNING)
            df_mapped = category_assignment_service.assign_categories(
                df=df_processed,
                category_clusters=cat_clusters,
                named_clusters=named_clusters,
            )

            # Stage 6: Exporting
            job_manager.update_status(job_id, JobStatus.EXPORTING)
            zip_path, export_stats = export_service.export_groups_to_zip(
                df=df_mapped,
                job_id=job_id,
                total_unique_categories=len(unique_cats),
            )

            # Mark completed with detailed result metrics
            job_result = {
                "ingest_stats": ingest_stats,
                "cluster_stats": cluster_stats,
                "export_stats": export_stats,
                "zip_path": zip_path,
            }
            job_manager.mark_completed(job_id, result=job_result)
            logger.info(f"Job {job_id} successfully completed.")

        except Exception as e:
            current_job = job_manager.get_job(job_id)
            current_stage = (
                current_job.status.value if current_job else "unknown"
            )
            error_msg = f"Failed at stage [{current_stage}]: {str(e)}"
            logger.error(f"Job {job_id} error: {error_msg}", exc_info=True)
            job_manager.mark_failed(job_id, error_message=error_msg)
        finally:
            if cleanup_uploaded_file and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass


orchestrator_service = OrchestratorService()
