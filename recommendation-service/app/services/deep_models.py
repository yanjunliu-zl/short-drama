"""
Industrial-Grade Deep Ranking Models — Douyin Standard

Models:
  1. TwoTowerModel — user tower + item tower for recall & pre-ranking
  2. DIN — Deep Interest Network for user behavior sequence attention
  3. MMOE — Multi-gate Mixture-of-Experts for multi-task learning

These models complement the existing Wide&Deep for production serving.
"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# ============================================================
# #1: Two-Tower Model (Recall & Pre-Ranking)
# ============================================================

if HAS_TORCH:

    class TwoTowerModel(nn.Module):
        """Dual-tower architecture for recall and pre-ranking.

        User Tower: user features → embedding (64-dim)
        Item Tower: item features → embedding (64-dim)
        Score: cosine(user_emb, item_emb)

        For recall: pre-compute item embeddings → FAISS ANN index
        For pre-rank: compute user embedding → ANN search → top-k
        """

        def __init__(self, user_feature_dim: int = 10, item_feature_dim: int = 8,
                     embedding_dim: int = 64, hidden_layers: List[int] = [256, 128]):
            super().__init__()
            # User tower
            user_layers = []
            prev = user_feature_dim
            for h in hidden_layers:
                user_layers.extend([nn.Linear(prev, h), nn.BatchNorm1d(h),
                                    nn.ReLU(), nn.Dropout(0.2)])
                prev = h
            user_layers.append(nn.Linear(prev, embedding_dim))
            self.user_tower = nn.Sequential(*user_layers)

            # Item tower
            item_layers = []
            prev = item_feature_dim
            for h in [128, 64]:  # Smaller tower for faster indexing
                item_layers.extend([nn.Linear(prev, h), nn.BatchNorm1d(h),
                                    nn.ReLU(), nn.Dropout(0.15)])
                prev = h
            item_layers.append(nn.Linear(prev, embedding_dim))
            self.item_tower = nn.Sequential(*item_layers)

            self._init_weights()

        def _init_weights(self):
            for m in self.modules():
                if isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)

        def forward_user(self, user_features: torch.Tensor) -> torch.Tensor:
            """Generate user embedding (for online inference)."""
            return F.normalize(self.user_tower(user_features), dim=-1)

        def forward_item(self, item_features: torch.Tensor) -> torch.Tensor:
            """Generate item embedding (for offline indexing)."""
            return F.normalize(self.item_tower(item_features), dim=-1)

        def forward(self, user_features: torch.Tensor,
                    item_features: torch.Tensor) -> torch.Tensor:
            """Score batch: dot product of normalized embeddings."""
            user_emb = self.forward_user(user_features)
            item_emb = self.forward_item(item_features)
            return torch.sum(user_emb * item_emb, dim=-1)  # cosine similarity

        def get_item_embeddings(self, item_features: np.ndarray) -> np.ndarray:
            """Batch compute item embeddings for FAISS indexing."""
            self.eval()
            with torch.no_grad():
                emb = self.forward_item(torch.tensor(item_features, dtype=torch.float32))
                return emb.cpu().numpy()


# ============================================================
# #2: DIN — Deep Interest Network (Sequence Attention)
# ============================================================

    class AttentionUnit(nn.Module):
        """DIN attention: computes attention weight of each historical behavior
        relative to the candidate item.
        """
        def __init__(self, embedding_dim: int, hidden_dim: int = 36):
            super().__init__()
            self.fc = nn.Sequential(
                nn.Linear(embedding_dim * 4, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
            )

        def forward(self, query: torch.Tensor, keys: torch.Tensor,
                    keys_length: torch.Tensor) -> torch.Tensor:
            """Attention-pooled user interest vector.

            Args:
                query: [B, D] candidate item embedding
                keys: [B, T, D] user historical behavior embeddings
                keys_length: [B] actual sequence length per user

            Returns:
                [B, D] pooled interest embedding
            """
            B, T, D = keys.shape
            # query: [B, 1, D] → broadcast to [B, T, D]
            query_expanded = query.unsqueeze(1).expand(-1, T, -1)
            # Outer product features
            outer = query_expanded * keys
            # Input to attention: [query, keys, query*keys, query-keys]
            attn_input = torch.cat([
                query_expanded, keys,
                outer, query_expanded - keys
            ], dim=-1)  # [B, T, 4D]

            attn_scores = self.fc(attn_input).squeeze(-1)  # [B, T]

            # Mask padding positions
            mask = torch.arange(T, device=keys.device).unsqueeze(0) < keys_length.unsqueeze(1)
            attn_scores = attn_scores.masked_fill(~mask, -1e9)

            attn_weights = F.softmax(attn_scores, dim=-1)  # [B, T]
            output = torch.bmm(attn_weights.unsqueeze(1), keys).squeeze(1)  # [B, D]
            return output


    class DINModel(nn.Module):
        """Deep Interest Network with user behavior sequence.

        Captures user's multi-interest from historical interactions.
        Each historical item embedding attends to the candidate item.

        Input:
          - user_features: [B, Fu] static user features
          - item_features: [B, Fi] candidate item features
          - behavior_seq: [B, T, Di] user's last T item embeddings
          - seq_length: [B] actual number of interactions per user

        Output: [B, 1] CTR score
        """

        def __init__(self, num_user_features: int = 10,
                     num_item_features: int = 8,
                     behavior_emb_dim: int = 32,
                     hidden_layers: List[int] = [200, 80]):
            super().__init__()
            self.attention = AttentionUnit(behavior_emb_dim)

            # MLP for final prediction
            # Input: user_features + item_features + attn_output + outer_product
            mlp_input_dim = (num_user_features + num_item_features +
                             behavior_emb_dim + behavior_emb_dim)
            layers = []
            prev = mlp_input_dim
            for h in hidden_layers:
                layers.extend([nn.Linear(prev, h), nn.BatchNorm1d(h),
                               nn.ReLU(), nn.Dropout(0.2)])
                prev = h
            layers.append(nn.Linear(prev, 1))
            self.mlp = nn.Sequential(*layers)

        def forward(self, user_features: torch.Tensor,
                    item_features: torch.Tensor,
                    behavior_seq: torch.Tensor,
                    seq_length: torch.Tensor) -> torch.Tensor:
            # DIN attention: pool user history relative to candidate item
            # Use item features projected to behavior_emb_dim as query
            item_emb = item_features[:, :min(item_features.shape[1], behavior_seq.shape[2])]
            if item_emb.shape[1] < behavior_seq.shape[2]:
                item_emb = F.pad(item_emb, (0, behavior_seq.shape[2] - item_emb.shape[1]))
            attn_out = self.attention(item_emb, behavior_seq, seq_length)

            # Outer product (element-wise) between attention output and item
            outer = attn_out * item_emb

            # Concatenate all features
            combined = torch.cat([user_features, item_features, attn_out, outer], dim=-1)
            return torch.sigmoid(self.mlp(combined)).squeeze(-1)

else:
    # Stubs when PyTorch unavailable
    class TwoTowerModel:
        def __init__(self, *args, **kwargs): pass

    class DINModel:
        def __init__(self, *args, **kwargs): pass


# ============================================================
# #3: MMOE — Multi-gate Mixture of Experts (Multi-Task)
# ============================================================

if HAS_TORCH:

    class MMOELayer(nn.Module):
        """MMOE layer: shared experts + task-specific gates.

        Each task gets a weighted combination of expert outputs.
        Experts learn shared representations; gates learn task-specific routing.
        """

        def __init__(self, input_dim: int, num_experts: int = 3,
                     expert_hidden: int = 128, num_tasks: int = 2):
            super().__init__()
            self.num_experts = num_experts
            self.num_tasks = num_tasks

            # Shared experts
            self.experts = nn.ModuleList([
                nn.Sequential(nn.Linear(input_dim, expert_hidden), nn.ReLU())
                for _ in range(num_experts)
            ])

            # Task-specific gates
            self.gates = nn.ModuleList([
                nn.Linear(input_dim, num_experts)
                for _ in range(num_tasks)
            ])

        def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
            """Returns list of task-specific representations."""
            expert_outputs = torch.stack(
                [expert(x) for expert in self.experts], dim=1
            )  # [B, num_experts, H]

            task_outputs = []
            for gate in self.gates:
                gate_weights = F.softmax(gate(x), dim=-1).unsqueeze(-1)  # [B, E, 1]
                task_out = torch.sum(expert_outputs * gate_weights, dim=1)  # [B, H]
                task_outputs.append(task_out)
            return task_outputs


    class MMOEModel(nn.Module):
        """MMOE multi-task ranking model.

        Shared feature extractor → MMOE layer → per-task towers.
        Tasks: CTR (click) + CVR (engagement/completion).

        Replaces the simple shared-bottom architecture with task-specific
        expert routing for better handling of task conflicts.
        """

        def __init__(self, num_continuous: int = 10,
                     categorical_vocabs: Dict[str, int] = None,
                     num_binary: int = 2,
                     embedding_dim: int = 8,
                     num_experts: int = 3,
                     expert_hidden: int = 128,
                     tower_hidden: List[int] = [64, 32]):
            super().__init__()
            if categorical_vocabs is None:
                categorical_vocabs = {"recall_source": 6, "genre": 20}

            # Embeddings
            self.embeddings = nn.ModuleDict({
                name: nn.Embedding(vocab_size, embedding_dim)
                for name, vocab_size in categorical_vocabs.items()
            })
            total_embed_dim = len(categorical_vocabs) * embedding_dim

            shared_input_dim = num_continuous + total_embed_dim

            # MMOE layer
            self.mmoe = MMOELayer(
                input_dim=shared_input_dim,
                num_experts=num_experts,
                expert_hidden=expert_hidden,
                num_tasks=2,  # CTR + CVR
            )

            # Task-specific towers
            self.ctr_tower = nn.Sequential(
                nn.Linear(expert_hidden, tower_hidden[0]), nn.ReLU(),
                nn.Linear(tower_hidden[0], tower_hidden[1]), nn.ReLU(),
                nn.Linear(tower_hidden[1], 1),
            )
            self.cvr_tower = nn.Sequential(
                nn.Linear(expert_hidden, tower_hidden[0]), nn.ReLU(),
                nn.Linear(tower_hidden[0], tower_hidden[1]), nn.ReLU(),
                nn.Linear(tower_hidden[1], 1),
            )

        def forward(self, continuous: torch.Tensor,
                    categorical: Dict[str, torch.Tensor],
                    binary: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """Returns (ctr_preds, cvr_preds)."""
            embed_outputs = [
                self.embeddings[name](categorical[name])
                for name in self.embeddings
            ]
            shared_input = torch.cat([continuous] + embed_outputs, dim=-1)

            ctr_rep, cvr_rep = self.mmoe(shared_input)

            ctr_pred = torch.sigmoid(self.ctr_tower(ctr_rep)).squeeze(-1)
            cvr_pred = torch.sigmoid(self.cvr_tower(cvr_rep)).squeeze(-1)
            return ctr_pred, cvr_pred

else:
    class MMOEModel:
        def __init__(self, *args, **kwargs): pass
