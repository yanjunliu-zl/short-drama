"""
Offline Evaluation Metrics — Douyin Standard

Metrics:
  - NDCG@K: Normalized Discounted Cumulative Gain (ranking quality)
  - Recall@K: whether relevant items appear in top-K
  - HitRate@K: fraction of users with at least one hit in top-K
  - MRR: Mean Reciprocal Rank
  - Coverage: fraction of catalog recommended
  - Personalization: inter-user diversity (1 - avg Jaccard)

Usage:
  from app.services.eval_metrics import evaluate
  result = evaluate(ground_truth, predictions)
  # → {"ndcg@10": 0.45, "recall@10": 0.32, "hit_rate@10": 0.78, ...}
"""
from typing import Dict, List, Set, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def dcg_at_k(scores: List[float], k: int) -> float:
    """Discounted Cumulative Gain at K."""
    scores = np.array(scores[:k], dtype=np.float64)
    if len(scores) == 0:
        return 0.0
    discounts = np.log2(np.arange(2, len(scores) + 2))
    return np.sum(scores / discounts)


def ndcg_at_k(ground_truth: List[str], predictions: List[str], k: int = 10) -> float:
    """Normalized DCG@K.

    Args:
        ground_truth: list of relevant item IDs (binary relevance = 1)
        predictions: list of recommended item IDs (ordered by score)
    """
    gt_set = set(ground_truth)
    relevance = [1.0 if pid in gt_set else 0.0 for pid in predictions[:k]]
    dcg = dcg_at_k(relevance, k)
    ideal = dcg_at_k(sorted(relevance, reverse=True), k)
    return dcg / ideal if ideal > 0 else 0.0


def recall_at_k(ground_truth: List[str], predictions: List[str], k: int = 10) -> float:
    """Recall@K: fraction of relevant items retrieved in top-K."""
    if not ground_truth:
        return 1.0
    gt_set = set(ground_truth)
    hits = sum(1 for pid in predictions[:k] if pid in gt_set)
    return hits / len(gt_set)


def hit_rate_at_k(ground_truth: List[str], predictions: List[str], k: int = 10) -> float:
    """HitRate@K: 1 if at least one relevant item in top-K, else 0."""
    gt_set = set(ground_truth)
    return 1.0 if any(pid in gt_set for pid in predictions[:k]) else 0.0


def mrr(ground_truth: List[str], predictions: List[str]) -> float:
    """Mean Reciprocal Rank of the first relevant item."""
    gt_set = set(ground_truth)
    for i, pid in enumerate(predictions):
        if pid in gt_set:
            return 1.0 / (i + 1)
    return 0.0


def coverage(predictions_per_user: List[List[str]], catalog_size: int) -> float:
    """Fraction of catalog that appears in at least one recommendation list."""
    recommended = set()
    for preds in predictions_per_user:
        recommended.update(preds)
    return len(recommended) / catalog_size if catalog_size > 0 else 0.0


def personalization(predictions_per_user: List[List[str]]) -> float:
    """Inter-user diversity: 1 - average Jaccard similarity between user lists."""
    if len(predictions_per_user) <= 1:
        return 0.0
    similarities = []
    for i in range(len(predictions_per_user)):
        for j in range(i + 1, len(predictions_per_user)):
            set_i = set(predictions_per_user[i])
            set_j = set(predictions_per_user[j])
            if set_i and set_j:
                jaccard = len(set_i & set_j) / len(set_i | set_j)
                similarities.append(jaccard)
    return 1.0 - np.mean(similarities) if similarities else 0.0


def evaluate(ground_truth: Dict[str, List[str]],  # user_id → relevant item IDs
             predictions: Dict[str, List[str]],    # user_id → recommended item IDs
             ks: List[int] = [5, 10, 20],
             catalog_size: int = None) -> Dict[str, float]:
    """Run full evaluation suite.

    Returns dict with metrics at each K value.

    Example:
      gt = {"user1": ["itemA","itemB"], "user2": ["itemC"]}
      preds = {"user1": ["itemA","itemX","itemB"], "user2": ["itemY","itemC"]}
      evaluate(gt, preds)
      # → {"ndcg@10": 0.75, "recall@10": 0.67, "hit_rate@10": 1.0, ...}
    """
    results = {}
    all_preds_list = []

    for k in ks:
        ndcg_list, recall_list, hit_list, mrr_list = [], [], [], []

        for user_id in ground_truth:
            gt_items = ground_truth.get(user_id, [])
            pred_items = predictions.get(user_id, [])
            all_preds_list.append(pred_items)

            ndcg_list.append(ndcg_at_k(gt_items, pred_items, k))
            recall_list.append(recall_at_k(gt_items, pred_items, k))
            hit_list.append(hit_rate_at_k(gt_items, pred_items, k))
            mrr_list.append(mrr(gt_items, pred_items))

        results[f"ndcg@{k}"] = round(np.mean(ndcg_list), 4) if ndcg_list else 0
        results[f"recall@{k}"] = round(np.mean(recall_list), 4) if recall_list else 0
        results[f"hit_rate@{k}"] = round(np.mean(hit_list), 4) if hit_list else 0
        results[f"mrr@{k}"] = round(np.mean(mrr_list), 4) if mrr_list else 0

    # Coverage and personalization (single value, not K-dependent)
    if catalog_size:
        results["coverage"] = round(coverage(all_preds_list, catalog_size), 4)
    results["personalization"] = round(personalization(all_preds_list), 4)
    results["num_users"] = len(ground_truth)

    logger.info(f"Eval: ndcg@10={results.get('ndcg@10', '?')}, "
                f"recall@10={results.get('recall@10', '?')}, "
                f"hit_rate@10={results.get('hit_rate@10', '?')}")
    return results
