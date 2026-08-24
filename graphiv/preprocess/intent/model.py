"""
The student model shared by training and inference

Importing this triggers no download, but pin_hf_cache must run before the model is built
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import torch
import torch.nn as nn
from transformers import AutoModel

from ._common import INTENTS, MODEL_NAME


class IntentStudent(nn.Module):
    """
    DistilBERT encoder with one intent head
    """

    backbone: nn.Module
    dropout: nn.Dropout
    intent_head: nn.Linear

    def __init__(
        self,
        n_intent: int = len(INTENTS),
    ) -> None:
        super().__init__()
        self.backbone = AutoModel.from_pretrained(MODEL_NAME)
        hidden = cast(int, self.backbone.config.hidden_size)  # pyright: ignore[reportAttributeAccessIssue]  # fmt: skip
        self.dropout = nn.Dropout(0.1)
        self.intent_head = nn.Linear(hidden, n_intent)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Return the intent logits for one batch
        """
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0]
        cls = self.dropout(cls)
        return self.intent_head(cls)


def load_student(ckpt: Path, device: torch.device) -> IntentStudent:
    """
    Build the student and load a checkpoint, dropping heads the current model no longer has
    """
    model = IntentStudent().to(device).eval()
    state = cast(dict[str, torch.Tensor], torch.load(ckpt, map_location=device, weights_only=True))
    own = set(model.state_dict())
    dropped = sorted(set(state) - own)
    if dropped:
        print(f"  dropping {len(dropped)} retired key(s): {', '.join(dropped)}", flush=True)
        state = {k: v for k, v in state.items() if k in own}
    _ = model.load_state_dict(state)
    return model
