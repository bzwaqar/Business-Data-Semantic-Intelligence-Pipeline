import logging
import time
from typing import Any, Dict, List, Tuple
import numpy as np
import umap
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from app.config import settings

logger = logging.getLogger(__name__)


class ClusteringService:
    """Service for UMAP dimensionality reduction and optimal K-Means clustering with bounded tier limits."""

    def cluster_unique_categories(
        self,
        category_embeddings: Dict[str, np.ndarray],
        total_rows: int = 0,
        umap_n_components: int = settings.UMAP_N_COMPONENTS,
        umap_metric: str = "cosine",
        min_k: int = settings.KMEANS_MIN_K,
        max_k: int = settings.KMEANS_MAX_K,
        step_k: int = settings.KMEANS_STEP_K,
    ) -> Tuple[Dict[str, int], Dict[str, Any]]:
        """Run UMAP dimensionality reduction followed by bounded K-Means clustering.

        TIER-BOUNDED CLUSTER LIMITS:
        - 20,000 to 50,000 rows: target 30 to 40 clusters max.
        - Above 50,000 rows (up to 1 lac / 100k+): target 40 to 70 clusters max.
        - Absolute upper bound cap: 70 clusters MAX.
        """
        start_time = time.perf_counter()
        categories = list(category_embeddings.keys())
        n_samples = len(categories)

        if n_samples == 0:
            return {}, {
                "categories_in": 0,
                "k_chosen": 0,
                "clusters_out": 0,
                "unclassified_count": 0,
                "time_taken_ms": 0.0,
                "cluster_stats": {},
            }

        X = np.array(
            [category_embeddings[cat] for cat in categories], dtype=np.float32
        )

        # Handle UMAP parameters for small sample sizes
        actual_n_components = min(umap_n_components, max(2, n_samples - 2))
        n_neighbors = min(15, max(2, n_samples - 1))

        if n_samples > 3:
            logger.info(
                f"Applying UMAP reduction on {n_samples} vectors: 384 -> {actual_n_components} components"
            )
            reducer = umap.UMAP(
                n_components=actual_n_components,
                n_neighbors=n_neighbors,
                metric=umap_metric,
                random_state=42,
            )
            X_reduced = reducer.fit_transform(X)
        else:
            X_reduced = X

        # Single category or minimal sample edge case handling
        if n_samples <= 2:
            best_k = n_samples
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init="auto")
            labels = kmeans.fit_predict(X_reduced)
            search_scores = {best_k: 1.0}
        else:
            # Estimate target K based on total dataset rows and unique category count
            if total_rows > 0:
                if total_rows < 20000:
                    tier_max_k = 30
                    k_target = max(4, min(30, int(round(n_samples / 12.0))))
                elif 20000 <= total_rows <= 50000:
                    tier_max_k = 40
                    k_target = max(30, min(40, int(round(n_samples / 20.0))))
                else:  # Above 50,000 rows (up to 100k+ / 1 lac)
                    tier_max_k = 70
                    k_target = max(40, min(70, int(round(n_samples / 15.0))))
            else:
                if n_samples <= 40:
                    tier_max_k = 15
                    k_target = max(2, int(round(n_samples / 6.0)))
                elif n_samples <= 150:
                    tier_max_k = 25
                    k_target = max(10, min(25, int(round(n_samples / 8.0))))
                elif n_samples <= 400:
                    tier_max_k = 40
                    k_target = max(25, min(40, int(round(n_samples / 10.0))))
                else:
                    tier_max_k = 70
                    k_target = max(40, min(70, int(round(n_samples / 12.0))))

            # Enforce strict tier max cap
            k_target = min(tier_max_k, min(max_k, k_target))

            # Determine local search window around k_target, strictly capped at tier_max_k
            lower_bound_k = max(2, min_k, int(round(k_target * 0.85)))
            upper_bound_k = min(tier_max_k, min(70, max_k, n_samples - 1, max(lower_bound_k + 1, int(round(k_target * 1.15)))))

            step = max(1, (upper_bound_k - lower_bound_k) // 10)
            candidate_ks = list(range(lower_bound_k, upper_bound_k + 1, step))

            logger.info(
                f"Tier-Bounded K-Estimation (Total Rows: {total_rows}, N={n_samples}): Target K={k_target}, Tier Max={tier_max_k}. "
                f"Searching optimal K in window [{lower_bound_k}..{upper_bound_k}] (step={step})..."
            )

            search_scores: Dict[int, float] = {}
            best_k = candidate_ks[0]
            best_score = -1.0

            for k in candidate_ks:
                km = KMeans(n_clusters=k, random_state=42, n_init="auto")
                cluster_labels = km.fit_predict(X_reduced)
                score = float(
                    silhouette_score(X_reduced, cluster_labels, metric="euclidean")
                )
                search_scores[k] = round(score, 4)
                logger.info(f"Candidate K={k}: Silhouette Score = {score:.4f}")

                if score > best_score:
                    best_score = score
                    best_k = k

            logger.info(
                f"Selected Optimal Bounded K={best_k} (Tier Cap: {tier_max_k}) with Silhouette Score = {best_score:.4f}"
            )
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init="auto")
            labels = kmeans.fit_predict(X_reduced)

        centroids = kmeans.cluster_centers_

        # Outlier detection: Identify categories whose distance to centroid is an extreme outlier
        if best_k > 1 and n_samples > 4:
            distances = np.linalg.norm(X_reduced - centroids[labels], axis=1)
            mean_dist = float(np.mean(distances))
            std_dist = float(np.std(distances))
            outlier_threshold = mean_dist + 2.5 * std_dist
            outliers_mask = distances > outlier_threshold
            labels[outliers_mask] = -1

        # Map category_string -> cluster_id (-1 for unclassified / "Others")
        category_clusters: Dict[str, int] = {
            cat: int(label) for cat, label in zip(categories, labels)
        }

        # Calculate per-cluster stats
        unique_labels = set(labels)
        cluster_stats: Dict[str, Any] = {}
        unclassified_count = int(np.sum(labels == -1))

        for cluster_id in range(best_k):
            mask = labels == cluster_id
            cluster_points = X_reduced[mask]
            count = int(np.sum(mask))

            if count > 0:
                dists = np.linalg.norm(
                    cluster_points - centroids[cluster_id], axis=1
                )
                avg_dist = float(np.mean(dists))
            else:
                avg_dist = 0.0

            cluster_stats[f"cluster_{cluster_id}"] = {
                "cluster_id": cluster_id,
                "size": count,
                "avg_centroid_distance": round(avg_dist, 4),
            }

        if unclassified_count > 0:
            cluster_stats["Others"] = {
                "cluster_id": -1,
                "size": unclassified_count,
                "avg_centroid_distance": 0.0,
            }

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        valid_clusters_count = len(unique_labels - {-1})

        logger.info(
            f"K-Means Clustering Complete - Categories in: {n_samples}, Optimal K: {best_k}, "
            f"Unclassified ('Others'): {unclassified_count}, Time: {elapsed_ms}ms"
        )

        stats = {
            "categories_in": n_samples,
            "k_chosen": best_k,
            "clusters_out": valid_clusters_count,
            "unclassified_count": unclassified_count,
            "k_search_scores": search_scores,
            "time_taken_ms": elapsed_ms,
            "cluster_stats": cluster_stats,
        }

        return category_clusters, stats


clustering_service = ClusteringService()
