"""Student model definition shared by train.py and infer.py.

Importing this module does NOT trigger transformers downloads — call
`pin_hf_cache()` from `phase_3.bert._common` before instantiating
`IntentStudent` so the HF cache lands under `data/models/hf_cache`.
"""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn
from transformers import AutoModel

from ._common import INTENTS, MODEL_NAME, POLARITIES


class IntentStudent(nn.Module):
    backbone: nn.Module
    dropout: nn.Dropout
    intent_head: nn.Linear
    polarity_head: nn.Linear

    def __init__(
        self,
        n_intent: int = len(INTENTS),
        n_polarity: int = len(POLARITIES),
    ) -> None:
        super().__init__()
        self.backbone = AutoModel.from_pretrained(MODEL_NAME)
        hidden = cast(int, self.backbone.config.hidden_size)  # pyright: ignore[reportAttributeAccessIssue]  # fmt: skip
        self.dropout = nn.Dropout(0.1)
        self.intent_head = nn.Linear(hidden, n_intent)
        self.polarity_head = nn.Linear(hidden, n_polarity)

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0]
        cls = self.dropout(cls)
        return self.intent_head(cls), self.polarity_head(cls)
