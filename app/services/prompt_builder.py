import json
from typing import Dict, List


class PromptBuilder:
    """Builds structured prompts for naming business category clusters via LLM."""

    def build_naming_prompt(self, clusters_batch: Dict[int, List[str]]) -> str:
        """Construct prompt for a batch of clusters to name them as JSON.

        Args:
            clusters_batch: Mapping of cluster_id -> list of member category strings.

        Returns:
            Formatted prompt string for Groq LLM.
        """
        cluster_data = []
        for cluster_id, items in clusters_batch.items():
            cluster_data.append(
                {
                    "cluster_id": cluster_id,
                    "sample_categories": items[:15],
                }
            )

        prompt = f"""You are an expert taxonomy and business category analyst.
Your task is to assign a clean, concise, standardized business category name for each group of related raw category strings below.

Input Clusters:
{json.dumps(cluster_data, indent=2)}

Instructions:
1. For each cluster_id, review its sample categories and generate a professional, standardized category name (e.g. "Plumbing Services", "Electrical Services", "HVAC & Climate Control").
2. Output ONLY a valid JSON object containing a "clusters" key with the array of results. Do not include extra text.
3. Every input cluster_id must be present in the output array.

Required JSON format:
{{
  "clusters": [
    {{"cluster_id": 0, "category_name": "Standardized Category Name"}},
    ...
  ]
}}
"""
        return prompt


prompt_builder = PromptBuilder()
