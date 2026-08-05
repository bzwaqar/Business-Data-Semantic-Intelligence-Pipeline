import logging
import os
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from app.config import settings

# Workaround for Intel OpenMP runtime duplication on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and caching L2-normalized embeddings for unique category strings."""

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._cache: Dict[str, np.ndarray] = {}

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def extract_unique_categories(
        self, df: pd.DataFrame, text_column: str = "normalized_text"
    ) -> Tuple[List[str], Dict[int, str]]:
        """Extract unique category strings and build row_id -> category_string mapping.

        Filters out 'Unclassified' placeholder strings from candidate list.

        Args:
            df: Ingested DataFrame containing row_id and normalized category text.
            text_column: Column name holding normalized category text.

        Returns:
            Tuple of (valid unique category strings list, dict mapping row_id -> category string).
        """
        row_map: Dict[int, str] = dict(zip(df["row_id"], df[text_column]))
        unique_categories: List[str] = [
            cat for cat in set(row_map.values()) if cat != "Unclassified"
        ]
        return unique_categories, row_map

    def embed_categories(
        self,
        categories: List[str],
        batch_size: int = 256,
    ) -> Dict[str, np.ndarray]:
        """Compute L2-normalized embeddings for unique category strings using caching.

        Args:
            categories: List of unique category strings.
            batch_size: Batch size for model inference.

        Returns:
            Dict mapping category string -> L2-normalized embedding vector.
        """
        uncached = [cat for cat in categories if cat not in self._cache]

        if uncached:
            logger.info(
                f"Embedding {len(uncached)} new unique category strings (batch size {batch_size})."
            )
            embeddings = self.model.encode(
                uncached,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            for cat, emb in zip(uncached, embeddings):
                self._cache[cat] = np.array(emb, dtype=np.float32)
        else:
            logger.info("All category embeddings retrieved from cache.")

        return {cat: self._cache[cat] for cat in categories}


embedding_service = EmbeddingService()
