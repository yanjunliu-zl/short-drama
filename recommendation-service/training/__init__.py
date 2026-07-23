"""
Recommendation Model Training — offline training pipeline, evaluation, and utilities.

Modules:
    trainer.py   — TrainingPipeline (data loading, feature engineering, training, versioning)
    metrics.py   — offline evaluation (NDCG@K, Recall@K, HitRate, MRR, Coverage)

Usage:
    from app.services.training import TrainingPipeline, evaluate

    # Training
    pipeline = TrainingPipeline(db_session=db)
    result = await pipeline.run(sample_limit=200000)

    # Evaluation
    from app.services.training.metrics import evaluate
    scores = evaluate(ground_truth, predictions)
"""
from .trainer import TrainingPipeline, run_scheduled_training, ModelVersion
from .metrics import evaluate, ndcg_at_k, recall_at_k, hit_rate_at_k, mrr

__all__ = [
    "TrainingPipeline",
    "run_scheduled_training",
    "ModelVersion",
    "evaluate",
    "ndcg_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "mrr",
]
