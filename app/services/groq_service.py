import json
import logging
import time
from typing import Dict, List, Optional
from groq import Groq
from app.config import settings
from app.services.prompt_builder import prompt_builder

logger = logging.getLogger(__name__)


class GroqService:
    """Service for batching cluster naming requests to Groq API with retries and fallback."""

    def __init__(self, api_key: str = settings.GROQ_API_KEY) -> None:
        self.api_key = api_key
        self.model_name = "llama-3.3-70b-versatile"
        self._client: Optional[Groq] = None

    @property
    def client(self) -> Optional[Groq]:
        """Lazy load Groq client if API key is present."""
        if self._client is None and self.api_key:
            self._client = Groq(api_key=self.api_key)
        return self._client

    def name_clusters(
        self,
        cluster_members: Dict[int, List[str]],
        max_batch_size: int = 50,
        max_retries: int = 2,
    ) -> Dict[int, str]:
        """Batch name clusters using Groq LLM with early-exit optimization for 'Others'.

        EARLY-EXIT CHECK:
        Any category/cluster already identified as belonging to the 'Others' group (cluster_id == -1
        or category name 'Unclassified' / 'Others') skips all Groq API requests, cluster matching,
        and category name generation, assigning 'Others' locally and instantly.

        Args:
            cluster_members: Mapping of cluster_id -> list of raw category strings.
            max_batch_size: Max number of clusters per API prompt batch (default 50).
            max_retries: Max retry attempts per batch call.

        Returns:
            Dict mapping cluster_id -> standardized category name string.
        """
        if not cluster_members:
            logger.info("Skipped Groq Calls (Others): 0")
            return {}

        named_clusters: Dict[int, str] = {}
        to_batch: Dict[int, List[str]] = {}
        skipped_others_count = 0

        # Early-exit check for "Others" / unclassified categories
        for cluster_id, members in cluster_members.items():
            if cluster_id == -1 or any(
                m.strip().lower() in ("others", "unclassified") for m in members
            ):
                named_clusters[cluster_id] = "Others"
                skipped_others_count += len(members)
                logger.info(
                    f"Early-exit check triggered: Cluster ID {cluster_id} ({len(members)} item(s)) "
                    f"assigned directly to 'Others'. Skipping Groq/LLM call."
                )
            else:
                to_batch[cluster_id] = members

        # Required logging metric format
        logger.info(f"Skipped Groq Calls (Others): {skipped_others_count}")

        if not to_batch:
            return named_clusters

        cluster_ids = list(to_batch.keys())
        batches = [
            cluster_ids[i : i + max_batch_size]
            for i in range(0, len(cluster_ids), max_batch_size)
        ]

        logger.info(
            f"Batching {len(to_batch)} active cluster(s) into {len(batches)} API call(s) (max {max_batch_size} per batch)."
        )

        for batch_index, batch_ids in enumerate(batches, start=1):
            sub_batch = {cid: to_batch[cid] for cid in batch_ids}
            prompt = prompt_builder.build_naming_prompt(sub_batch)
            batch_result = self._process_batch_with_retry(
                prompt=prompt,
                sub_batch=sub_batch,
                batch_index=batch_index,
                max_retries=max_retries,
            )
            named_clusters.update(batch_result)

        return named_clusters

    def _process_batch_with_retry(
        self,
        prompt: str,
        sub_batch: Dict[int, List[str]],
        batch_index: int,
        max_retries: int,
    ) -> Dict[int, str]:
        """Execute Groq API call for a batch with retry logic and per-cluster fallback."""
        if not self.api_key or self.client is None:
            logger.warning(
                f"Batch {batch_index}: GROQ_API_KEY not configured or client unavailable. Using fallback cluster names."
            )
            return self._fallback_batch_names(sub_batch)

        for attempt in range(1, max_retries + 2):
            try:
                logger.info(
                    f"Calling Groq API (Batch {batch_index}, Attempt {attempt}/{max_retries + 1})..."
                )
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                raw_text = response.choices[0].message.content or ""
                return self._parse_and_validate_response(raw_text, sub_batch)
            except Exception as e:
                logger.warning(
                    f"Groq API call attempt {attempt} failed for batch {batch_index}: {e}"
                )
                if attempt <= max_retries:
                    time.sleep(1.0 * attempt)

        logger.error(
            f"Batch {batch_index}: All API retries failed. Falling back to raw category names."
        )
        return self._fallback_batch_names(sub_batch)

    def _parse_and_validate_response(
        self, raw_text: str, sub_batch: Dict[int, List[str]]
    ) -> Dict[int, str]:
        """Parse LLM JSON response and validate each cluster_id name, applying fallback if missing."""
        result_names: Dict[int, str] = {}
        try:
            parsed = json.loads(raw_text)
            items = (
                parsed
                if isinstance(parsed, list)
                else parsed.get(
                    "clusters", parsed.get("categories", parsed.get("data", []))
                )
            )

            llm_map: Dict[int, str] = {}
            if isinstance(items, list):
                for item in items:
                    if (
                        isinstance(item, dict)
                        and "cluster_id" in item
                        and "category_name" in item
                    ):
                        llm_map[int(item["cluster_id"])] = str(
                            item["category_name"]
                        ).strip()
            elif isinstance(parsed, dict):
                for k, v in parsed.items():
                    try:
                        cid = int(k)
                        if isinstance(v, str):
                            llm_map[cid] = v.strip()
                        elif isinstance(v, dict) and "category_name" in v:
                            llm_map[cid] = str(v["category_name"]).strip()
                    except ValueError:
                        continue

            for cid, members in sub_batch.items():
                if cid in llm_map and llm_map[cid]:
                    result_names[cid] = llm_map[cid]
                else:
                    fallback_name = members[0] if members else "Others"
                    logger.warning(
                        f"Cluster {cid} name missing in LLM response. Fallback to: '{fallback_name}'"
                    )
                    result_names[cid] = fallback_name

        except Exception as e:
            logger.warning(
                f"Failed to parse LLM JSON response: {e}. Applying fallback to batch clusters."
            )
            return self._fallback_batch_names(sub_batch)

        return result_names

    @staticmethod
    def _fallback_batch_names(sub_batch: Dict[int, List[str]]) -> Dict[int, str]:
        """Fallback helper returning the first raw category string for each cluster."""
        fallback: Dict[int, str] = {}
        for cid, members in sub_batch.items():
            fallback[cid] = members[0] if members else f"Cluster {cid}"
        return fallback


groq_service = GroqService()
