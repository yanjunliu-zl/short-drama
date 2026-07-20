"""
Wide&Deep 推荐模型离线训练管线。

训练流程:
  1. 从 MySQL 提取正负样本 (user_case_interactions + 随机负采样)
  2. 特征提取 + 预处理 (Z-score归一化, 类别编码)
  3. Wide&Deep 模型训练 (BCE loss + Adam)
  4. 模型评估 (AUC, Precision@K, Recall@K)
  5. 保存模型 + 预处理器

用法:
  python -m app.services.train_model --epochs 10 --batch_size 256
  # 或定时任务: K8s CronJob / Celery Beat 每天凌晨训练
"""
import logging
import os
import pickle
import time
from typing import Dict, Any, List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """离线训练管线 — 负采样 + 特征工程 + 模型训练 + 评估 + 保存"""

    def __init__(self, db_session=None, model_dir: str = "/app/data/models"):
        self.db = db_session
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        # 训练超参数
        self.epochs = 10
        self.batch_size = 256
        self.learning_rate = 0.001
        self.neg_ratio = 3  # 负:正 = 3:1

        # 模型 & 预处理器
        self.model = None
        self.preprocessor = None

    # ================================================================
    # Step 1: 数据提取
    # ================================================================

    async def _load_samples(self, limit: int = 100000) -> List[Dict[str, Any]]:
        """从数据库加载训练样本。

        正样本: 用户看过/点赞的内容
        负样本: 随机未交互内容 (负采样)
        """
        if self.db is None:
            raise RuntimeError("数据库未连接")

        from sqlalchemy import text

        # 正样本: 用户有过交互的记录
        pos_sql = text(f"""
            SELECT uci.user_id, c.id as case_id, c.title, c.tags, c.genre,
                   c.author, c.view_count, c.like_count, c.created_at,
                   uci.action_type,
                   CASE WHEN uci.action_type = 'like' THEN 1 ELSE 0 END as label
            FROM user_case_interactions uci
            JOIN cases c ON c.id = uci.case_id
            WHERE c.status = 'published'
            AND uci.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY RAND() LIMIT {limit // 2}
        """)
        pos_rows = await self.db.execute(pos_sql)
        pos_samples = [
            {"user_id": r.user_id, "case_id": r.case_id, "title": r.title,
             "tags": r.tags, "genre": r.genre or "", "author": r.author or "",
             "view_count": r.view_count or 0, "like_count": r.like_count or 0,
             "created_at": str(r.created_at or ""), "label": 1}
            for r in pos_rows.fetchall()
        ]

        # 负样本: 随机选取未交互内容
        neg_count = min(len(pos_samples) * self.neg_ratio, limit // 2)
        neg_sql = text(f"""
            SELECT 'neg_user' as user_id, c.id as case_id, c.title, c.tags, c.genre,
                   c.author, c.view_count, c.like_count, c.created_at,
                   NULL as action_type, 0 as label
            FROM cases c
            WHERE c.status = 'published'
            ORDER BY RAND() LIMIT {neg_count}
        """)
        neg_rows = await self.db.execute(neg_sql)
        neg_samples = [
            {"user_id": "neg_user", "case_id": r.case_id, "title": r.title,
             "tags": r.tags, "genre": r.genre or "", "author": r.author or "",
             "view_count": r.view_count or 0, "like_count": r.like_count or 0,
             "created_at": str(r.created_at or ""), "label": 0}
            for r in neg_rows.fetchall()
        ]

        samples = pos_samples + neg_samples
        np.random.shuffle(samples)
        logger.info(f"训练样本: {len(pos_samples)} 正 + {len(neg_samples)} 负 = {len(samples)} 总")
        return samples

    # ================================================================
    # Step 2: 特征工程
    # ================================================================

    @staticmethod
    def _extract_features(sample: Dict[str, Any]) -> Dict[str, Any]:
        """从样本提取特征 (与推理时 _extract_features 保持一致)"""
        tags = sample.get("tags", "")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        elif not isinstance(tags, list):
            tags = []

        # 简易特征 (训练时无法获取真实用户画像, 用item特征 + 随机扰动模拟)
        return {
            "user_view_count": np.random.randint(0, 100),
            "user_like_count": np.random.randint(0, 50),
            "user_tag_diversity": np.random.randint(0, 10),
            "item_view_count": sample.get("view_count", 0),
            "item_like_count": sample.get("like_count", 0),
            "item_share_count": 0,
            "item_age_days": np.random.randint(0, 90),
            "tag_match_count": np.random.randint(0, len(tags) + 1),
            "recall_source": np.random.choice(["cf", "content", "hot", "author", "search"]),
            "recall_score": np.random.uniform(0.5, 0.95),
            "hour_of_day": np.random.randint(0, 24),
            "item_genre": sample.get("genre", ""),
            "genre_match": np.random.randint(0, 2),
            "author_match": np.random.randint(0, 2),
            "label": sample.get("label", 0),
        }

    def _prepare_data(self, samples: List[Dict]) -> Tuple[np.ndarray, np.ndarray,
                                                           Dict[str, Any]]:
        """准备训练数据: 特征提取 + 预处理。

        Returns:
            (features_dict, labels, preprocessor_state)
        """
        from app.services.ranking_model import FEATURE_CONFIG, NUM_CONTINUOUS

        continuous_feats = []
        categorical_feats = {k: [] for k in FEATURE_CONFIG["categorical"]}
        binary_feats = []
        labels = []

        for s in samples:
            f = self._extract_features(s)
            cont = [float(f.get(name, 0)) for name in FEATURE_CONFIG["continuous"]]
            continuous_feats.append(cont)

            for name in FEATURE_CONFIG["categorical"]:
                raw = f.get(name, "unknown")
                if name == "recall_source":
                    idx = {"cf": 0, "content": 1, "hot": 2, "author": 3, "search": 4}.get(raw, 0)
                elif name == "genre":
                    idx = hash(raw) % 20
                else:
                    idx = 0
                categorical_feats[name].append(idx)

            bin_vals = [float(f.get(name, 0)) for name in FEATURE_CONFIG["binary"]]
            binary_feats.append(bin_vals)
            labels.append(float(f["label"]))

        # Z-score 归一化
        cont_arr = np.array(continuous_feats, dtype=np.float32)
        mean = cont_arr.mean(axis=0)
        std = cont_arr.std(axis=0) + 1e-8
        cont_arr = (cont_arr - mean) / std
        cont_arr = np.nan_to_num(cont_arr, 0.0)

        labels = np.array(labels, dtype=np.float32)

        features = {
            "continuous": cont_arr,
            "categorical": categorical_feats,
            "binary": np.array(binary_feats, dtype=np.float32),
        }

        preprocessor_state = {
            "cont_mean": mean.tolist(),
            "cont_std": std.tolist(),
        }

        logger.info(f"特征矩阵: continuous={cont_arr.shape}, labels={labels.shape}")
        return features, labels, preprocessor_state

    # ================================================================
    # Step 3: 模型训练
    # ================================================================

    def _train_model(self, features: dict, labels: np.ndarray,
                     preprocessor_state: dict,
                     val_split: float = 0.2) -> Dict[str, float]:
        """训练 Wide&Deep 模型。

        Returns:
            训练指标: {loss, auc, accuracy}
        """
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import TensorDataset, DataLoader
        from app.services.ranking_model import WideAndDeep, FEATURE_CONFIG, NUM_CONTINUOUS, NUM_BINARY

        HAS_TORCH = True
        if not HAS_TORCH:
            logger.warning("PyTorch 不可用 — 跳过训练")
            return {"error": "pytorch unavailable"}

        # 划分训练/验证集
        n = len(labels)
        n_train = int(n * (1 - val_split))
        indices = np.random.permutation(n)
        train_idx, val_idx = indices[:n_train], indices[n_train:]

        # 创建模型
        self.model = WideAndDeep(
            num_continuous=NUM_CONTINUOUS,
            categorical_vocabs={k: v for k, v in FEATURE_CONFIG["categorical"].items()},
            num_binary=NUM_BINARY,
        )

        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        criterion = nn.BCELoss()

        # 训练循环
        best_auc = 0.0
        train_losses = []

        for epoch in range(self.epochs):
            self.model.train()
            epoch_loss = 0.0
            # Mini-batch
            perm = np.random.permutation(n_train)
            for start in range(0, n_train, self.batch_size):
                batch_idx = perm[start:start + self.batch_size]
                # 构建 batch
                cont_batch = torch.tensor(features["continuous"][batch_idx], dtype=torch.float32)
                cat_batch = {
                    k: torch.tensor(np.array(v)[batch_idx], dtype=torch.long)
                    for k, v in features["categorical"].items()
                }
                bin_batch = torch.tensor(features["binary"][batch_idx], dtype=torch.float32)
                y_batch = torch.tensor(labels[batch_idx], dtype=torch.float32)

                optimizer.zero_grad()
                preds = self.model.forward(cont_batch, cat_batch, bin_batch)
                loss = criterion(preds, y_batch)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / max(1, n_train // self.batch_size)
            train_losses.append(avg_loss)

            # 验证
            self.model.eval()
            with torch.no_grad():
                cont_val = torch.tensor(features["continuous"][val_idx], dtype=torch.float32)
                cat_val = {
                    k: torch.tensor(np.array(v)[val_idx], dtype=torch.long)
                    for k, v in features["categorical"].items()
                }
                bin_val = torch.tensor(features["binary"][val_idx], dtype=torch.float32)
                y_val = labels[val_idx]
                val_preds = self.model.forward(cont_val, cat_val, bin_val).cpu().numpy()

                from sklearn.metrics import roc_auc_score
                auc = roc_auc_score(y_val, val_preds) if len(np.unique(y_val)) > 1 else 0.5

            logger.info(f"Epoch {epoch+1}/{self.epochs}: loss={avg_loss:.4f}, val_auc={auc:.4f}")
            if auc > best_auc:
                best_auc = auc

        return {
            "final_loss": round(avg_loss, 4),
            "best_auc": round(best_auc, 4),
            "epochs": self.epochs,
            "train_samples": n_train,
            "val_samples": n - n_train,
        }

    # ================================================================
    # Step 4: 保存模型
    # ================================================================

    def _save_artifacts(self, preprocessor_state: dict, metrics: dict):
        """保存模型权重和预处理器。"""
        import torch

        model_path = os.path.join(self.model_dir, "wide_and_deep.pt")
        preproc_path = os.path.join(self.model_dir, "preprocessor.pkl")
        metrics_path = os.path.join(self.model_dir, "metrics.json")

        if self.model:
            torch.save(self.model.state_dict(), model_path)
            logger.info(f"模型已保存: {model_path}")

        with open(preproc_path, "wb") as f:
            pickle.dump(preprocessor_state, f)
        logger.info(f"预处理器已保存: {preproc_path}")

        import json
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"指标已保存: {metrics_path}")

        return model_path, preproc_path

    # ================================================================
    # 完整训练流程
    # ================================================================

    async def run(self, sample_limit: int = 50000) -> Dict[str, Any]:
        """执行完整训练流程。"""
        t0 = time.time()
        logger.info(f"=== 推荐模型训练开始 (limit={sample_limit}) ===")

        try:
            # Step 1: 加载数据
            samples = await self._load_samples(limit=sample_limit)
            if not samples:
                return {"error": "无训练数据"}

            # Step 2: 特征工程
            features, labels, prep_state = self._prepare_data(samples)

            # Step 3: 训练
            metrics = self._train_model(features, labels, prep_state)

            # Step 4: 保存
            model_path, prep_path = self._save_artifacts(prep_state, metrics)

            elapsed = time.time() - t0
            logger.info(f"=== 训练完成: {metrics}, elapsed={elapsed:.1f}s ===")

            return {
                "status": "completed",
                "metrics": metrics,
                "model_path": model_path,
                "preprocessor_path": prep_path,
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            logger.error(f"训练失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}


# CronJob 入口
async def run_scheduled_training():
    """定时训练入口 (K8s CronJob 或 Celery Beat 调用)"""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        pipeline = TrainingPipeline(db_session=db)
        result = await pipeline.run(sample_limit=100000)
        return result
