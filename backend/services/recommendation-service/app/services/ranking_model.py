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
        self.model = WideAndDeep(
            num_continuous=NUM_CONTINUOUS,
            categorical_vocabs={k: v for k, v in FEATURE_CONFIG["categorical"].items()},
            num_binary=NUM_BINARY,
        )
        if model_path and os.path.exists(model_path):
            self.model.load(model_path)
        else:
            self.model.eval()
        if preprocessor_path and os.path.exists(preprocessor_path):
            self.preprocessor.load(preprocessor_path)
        logger.info("Wide&Deep 模型已初始化 (has_torch=%s)", HAS_TORCH)

    def rank(self, features_list: List[Dict]) -> List[float]:
        if not HAS_TORCH or self.model is None:
            return [0.0] * len(features_list)
        return [0.0] * len(features_list)  # 需要训练后才能给出有意义的分数


_ranking_service: Optional[RankingService] = None


def get_ranking_service() -> RankingService:
    global _ranking_service
    if _ranking_service is None:
        _ranking_service = RankingService()
        _ranking_service.initialize()
    return _ranking_service
