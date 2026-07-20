"""
Wide & Deep Learning 排序模型 — CTR 预估

当 PyTorch 可用时: 使用 Wide&Deep 神经网络
当 PyTorch 不可用时: 返回 0, 由推荐引擎降级为加权 CTR 公式
"""
import logging
import os
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---- PyTorch 可选 ----
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    nn = None
    F = None

# ==================== Feature Config ====================

FEATURE_CONFIG = {
    "continuous": [
        "user_view_count", "user_like_count", "user_tag_diversity",
        "item_view_count", "item_like_count", "item_share_count",
        "item_age_days", "tag_match_count", "recall_score", "hour_of_day",
    ],
    "categorical": {"recall_source": 6, "genre": 20},
    "binary": ["genre_match", "author_match"],
}

NUM_CONTINUOUS = len(FEATURE_CONFIG["continuous"])
NUM_CATEGORICAL = len(FEATURE_CONFIG["categorical"])
NUM_BINARY = len(FEATURE_CONFIG["binary"])


# ==================== Wide & Deep Model ====================

if HAS_TORCH:

    class WideAndDeep(nn.Module):
        def __init__(
            self,
            num_continuous: int = 10,
            categorical_vocabs: Dict[str, int] = None,
            num_binary: int = 2,
            embedding_dim: int = 8,
            deep_layers: List[int] = [256, 128, 64],
            dropout: float = 0.2,
        ):
            super().__init__()
            if categorical_vocabs is None:
                categorical_vocabs = {"recall_source": 6, "genre": 20}

            self.embeddings = nn.ModuleDict({
                name: nn.Embedding(vocab_size, embedding_dim)
                for name, vocab_size in categorical_vocabs.items()
            })
            total_embed_dim = len(categorical_vocabs) * embedding_dim

            deep_input_dim = num_continuous + total_embed_dim
            layers = []
            prev = deep_input_dim
            for h in deep_layers:
                layers.extend([nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)])
                prev = h
            self.deep = nn.Sequential(*layers)

            wide_input_dim = num_continuous + num_binary + len(categorical_vocabs)
            self.wide = nn.Linear(wide_input_dim, 1)
            self.final = nn.Linear(deep_layers[-1] + 1, 1)
            self._init_weights()

        def _init_weights(self):
            for m in self.modules():
                if isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)
                elif isinstance(m, nn.Embedding):
                    nn.init.uniform_(m.weight, -0.01, 0.01)

        def forward(self, continuous, categorical, binary):
            embed_outputs = [self.embeddings[name](categorical[name]) for name in self.embeddings]
            deep_input = torch.cat([continuous] + embed_outputs, dim=-1)
            deep_out = self.deep(deep_input)
            wide_input = torch.cat([continuous, binary] + embed_outputs, dim=-1)
            wide_out = self.wide(wide_input)
            return torch.sigmoid(self.final(torch.cat([deep_out, wide_out], dim=-1))).squeeze(-1)

        def save(self, path: str):
            torch.save(self.state_dict(), path)

        def load(self, path: str):
            self.load_state_dict(torch.load(path, map_location="cpu"))
            self.eval()

else:
    # PyTorch 不可用时的占位
    class WideAndDeep:
        def __init__(self, *args, **kwargs): pass
        def save(self, path): pass
        def load(self, path): pass


# ==================== Feature Preprocessor ====================

class FeaturePreprocessor:
    def __init__(self):
        self.cont_mean: np.ndarray = None
        self.cont_std: np.ndarray = None
        self.genre_map: Dict[str, int] = {}
        self._next_genre_id = 1

    def fit(self, samples: List[Dict]):
        cont_vals = [[s.get(f, 0) for f in FEATURE_CONFIG["continuous"]] for s in samples]
        arr = np.array(cont_vals, dtype=np.float32)
        self.cont_mean = arr.mean(axis=0)
        self.cont_std = arr.std(axis=0) + 1e-8
        for s in samples:
            g = s.get("item_genre", "unknown")
            if g not in self.genre_map:
                self.genre_map[g] = self._next_genre_id
                self._next_genre_id += 1

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({"mean": self.cont_mean, "std": self.cont_std, "genre_map": self.genre_map}, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            d = pickle.load(f)
            self.cont_mean = d["mean"]
            self.cont_std = d["std"]
            self.genre_map = d.get("genre_map", {})


# ==================== Inference Service ====================

class RankingService:
    def __init__(self):
        self.model: Optional[WideAndDeep] = None
        self.preprocessor = FeaturePreprocessor()

    def initialize(self, model_path: str = "", preprocessor_path: str = ""):
        if not HAS_TORCH:
            logger.info("PyTorch 不可用 — 使用降级 CTR 加权公式")
            return

        # Auto-detect trained model in default dir
        default_dir = "/app/data/models"
        if not model_path:
            candidate = os.path.join(default_dir, "wide_and_deep.pt")
            if os.path.exists(candidate):
                model_path = candidate
        if not preprocessor_path:
            candidate = os.path.join(default_dir, "preprocessor.pkl")
            if os.path.exists(candidate):
                preprocessor_path = candidate

        self.model = WideAndDeep(
            num_continuous=NUM_CONTINUOUS,
            categorical_vocabs={k: v for k, v in FEATURE_CONFIG["categorical"].items()},
            num_binary=NUM_BINARY,
        )
        if model_path and os.path.exists(model_path):
            self.model.load(model_path)
            logger.info(f"模型已加载: {model_path}")
        else:
            self.model.eval()
            logger.info("使用随机初始化模型 (待训练)")
        if preprocessor_path and os.path.exists(preprocessor_path):
            self.preprocessor.load(preprocessor_path)
            logger.info(f"预处理器已加载: {preprocessor_path}")
        else:
            logger.info("预处理器未找到 — 特征不做归一化")
        logger.info("Wide&Deep 模型已初始化 (has_torch=%s)", HAS_TORCH)

    def rank(self, features_list: List[Dict]) -> List[float]:
        """Score candidates using Wide&Deep model with feature normalization.

        If the model or preprocessor is not ready, returns zeros
        to trigger the fallback weighted formula in RankingLayer.

        Args:
            features_list: List of feature dicts from _extract_features().

        Returns:
            List of CTR scores (0.0-1.0) or zeros for fallback.
        """
        if not HAS_TORCH or self.model is None:
            return [0.0] * len(features_list)

        if not features_list:
            return []

        try:
            # 1. Extract feature arrays
            continuous_feats = []
            categorical_feats = {k: [] for k in FEATURE_CONFIG["categorical"]}
            binary_feats = []

            for f in features_list:
                cont = [float(f.get(name, 0)) for name in FEATURE_CONFIG["continuous"]]
                continuous_feats.append(cont)

                cat = {}
                for name in FEATURE_CONFIG["categorical"]:
                    raw_val = f.get(name, "unknown")
                    # Map string to index for recall_source and genre
                    if name == "recall_source":
                        cat[name] = {"cf": 0, "content": 1, "hot": 2, "author": 3, "search": 4}.get(raw_val, 0)
                    elif name == "genre":
                        cat[name] = self.preprocessor.genre_map.get(raw_val, 0)
                    else:
                        cat[name] = 0
                    categorical_feats[name].append(cat[name])

                bin_vals = [float(f.get(name, 0)) for name in FEATURE_CONFIG["binary"]]
                binary_feats.append(bin_vals)

            # 2. Normalize continuous features
            cont_arr = np.array(continuous_feats, dtype=np.float32)
            if self.preprocessor.cont_mean is not None:
                cont_arr = (cont_arr - self.preprocessor.cont_mean) / self.preprocessor.cont_std
            cont_arr = np.nan_to_num(cont_arr, nan=0.0, posinf=0.0, neginf=0.0)

            # 3. Convert to tensors
            continuous_t = torch.tensor(cont_arr, dtype=torch.float32)
            categorical_t = {
                name: torch.tensor(vals, dtype=torch.long)
                for name, vals in categorical_feats.items()
            }
            binary_t = torch.tensor(binary_feats, dtype=torch.float32)

            # 4. Run model
            with torch.no_grad():
                scores = self.model.forward(continuous_t, categorical_t, binary_t)

            # 5. Convert to Python floats, clamp to [0, 1]
            result = scores.cpu().numpy().tolist()
            if isinstance(result, float):
                result = [result]
            result = [max(0.0, min(1.0, float(s))) for s in result]

            # Validate: if all scores are 0 or NaN, signal fallback
            if all(s <= 1e-6 for s in result) or any(np.isnan(s) for s in result):
                logger.debug("Model returned degenerate scores — using fallback")
                return [0.0] * len(features_list)

            logger.debug(f"Wide&Deep scored {len(result)} items, "
                         f"range=[{min(result):.4f}, {max(result):.4f}]")
            return result

        except Exception as e:
            logger.warning(f"Wide&Deep ranking failed: {e} — using fallback")
            return [0.0] * len(features_list)


_ranking_service: Optional[RankingService] = None


def get_ranking_service() -> RankingService:
    global _ranking_service
    if _ranking_service is None:
        _ranking_service = RankingService()
        _ranking_service.initialize()
    return _ranking_service
