import logging
from typing import Dict
import pandas as pd

logger = logging.getLogger(__name__)


class CategoryAssignmentService:
    """Service for mapping original DataFrame rows to standardized cluster group names."""

    def assign_categories(
        self,
        df: pd.DataFrame,
        category_clusters: Dict[str, int],
        named_clusters: Dict[int, str],
        text_column: str = "normalized_text",
    ) -> pd.DataFrame:
        """Map every row in df to a group_name using category_clusters and named_clusters lookups.

        Unclassified or unmapped categories and rows with missing category text are automatically assigned to 'Others'.
        """
        # Build direct lookup: normalized_text -> group_name
        text_to_group: Dict[str, str] = {
            "Unclassified": "Others"
        }
        for text, cluster_id in category_clusters.items():
            text_to_group[text] = named_clusters.get(cluster_id, "Others")

        df_mapped = df.copy()
        # Map category text to group name, defaulting any missing/unclassified category to "Others"
        df_mapped["group_name"] = df_mapped[text_column].map(text_to_group).fillna("Others")

        logger.info(
            f"Successfully assigned {len(df_mapped)} rows across {df_mapped['group_name'].nunique()} unique groups (including 'Others' if applicable)."
        )
        return df_mapped


category_assignment_service = CategoryAssignmentService()
