"""The original Nomic v2 MoE query space, encoded inside the CPU backend."""

from __future__ import annotations

import json
import math
import re
import threading
from pathlib import Path
from typing import Any

MODEL_ID = "nomic-ai/nomic-embed-text-v2-moe"
CODE_REPOSITORY = "nomic-ai/nomic-bert-2048"
MODEL_REVISION = "1066b6599d099fbb93dfcb64f9c37a7c9e503e85"
CODE_REVISION = "7710840340a098cfb869c4f65e87cf2b1b70caca"
DIMENSION = 768
MAX_TOKENS = 512
QUERY_PREFIX = "search_query: "
DOCUMENT_PREFIX = "search_document: "
MODEL_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
)


class NomicQueryEncoder:
    """Load pinned official weights once, then mean-pool 768-dimensional CPU queries.

    Imports and model downloads are lazy. Call ``load`` before readiness to
    validate the real forward pass. Inference is serialized to bound activation
    memory and protect the model's mutable rotary-position caches.
    """

    def __init__(
        self,
        model_id: str = MODEL_ID,
        cache: Path | None = None,
        *,
        model_path: Path | None = None,
        threads: int = 4,
        revision: str = MODEL_REVISION,
        code_revision: str = CODE_REVISION,
    ) -> None:
        """Configure a compatible local encoder without downloading or importing Torch.

        Args:
            model_id: The canonical model name or its existing short alias.
            cache: Writable persistent model cache, normally an Azure Files mount.
            model_path: Optional already-materialized official model directory.
            threads: Maximum Torch intra-operation CPU threads.
            revision: Immutable official weight/tokenizer commit.
            code_revision: Immutable commit of Nomic's separate architecture repository.
        """
        if model_id not in {MODEL_ID, "nomic-embed-text-v2-moe"}:
            raise ValueError("Local queries require the existing nomic-embed-text-v2-moe model")
        if not isinstance(threads, int) or isinstance(threads, bool) or threads < 1:
            raise ValueError("Nomic CPU thread count must be a positive integer")
        if not re.fullmatch(r"[a-f0-9]{40}", revision) or not re.fullmatch(
            r"[a-f0-9]{40}", code_revision
        ):
            raise ValueError("Nomic weights and architecture code must use immutable commit hashes")
        self.model_id = MODEL_ID
        self.dimension = DIMENSION
        self.cache = Path(cache or Path.home() / ".cache" / "graphiv" / "nomic").resolve()
        self.model_path = Path(model_path).resolve() if model_path is not None else None
        self.threads = threads
        self.revision = revision
        self.code_revision = code_revision
        self._lock = threading.RLock()
        self._model: Any = None
        self._tokenizer: Any = None

    def _directory(self) -> Path:
        if self.model_path is not None:
            directory = self.model_path
        else:
            from huggingface_hub import snapshot_download

            directory = self.cache / f"model-{self.revision}"
            marker = directory / ".graphiv-model.json"
            expected = {"repository": MODEL_ID, "revision": self.revision}
            complete = False
            if marker.is_file():
                try:
                    complete = json.loads(marker.read_text()) == expected
                except (OSError, ValueError):
                    complete = False
            complete = complete and all((directory / name).is_file() for name in MODEL_FILES)
            if not complete:
                self.cache.mkdir(parents=True, exist_ok=True)
                snapshot_download(
                    repo_id=MODEL_ID,
                    revision=self.revision,
                    local_dir=str(directory),
                    allow_patterns=list(MODEL_FILES),
                )
                marker.write_text(json.dumps(expected) + "\n", encoding="utf-8")
        if not all((directory / name).is_file() for name in MODEL_FILES):
            raise ValueError("The local Nomic directory is missing its weights or tokenizer files")
        return directory

    def load(self) -> None:
        """Load exact pinned CPU weights and validate a real prefixed forward pass.

        No alternate embedding provider is used when loading fails. Meta-device
        parameter construction followed by ``assign=True`` avoids retaining a
        second, randomly initialized 1.9 GB model during weight loading.
        """
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from accelerate import init_empty_weights
                from safetensors.torch import load_file
                from transformers import AutoConfig, AutoTokenizer
                from transformers.dynamic_module_utils import get_class_from_dynamic_module
            except ImportError as error:
                raise RuntimeError(
                    "Install the nomic extra for local Nomic CPU encoding"
                ) from error
            torch.set_num_threads(self.threads)
            directory = self._directory()
            hub = str(self.cache / "architecture")
            config = AutoConfig.from_pretrained(
                str(directory),
                trust_remote_code=True,
                code_revision=self.code_revision,
                cache_dir=hub,
            )
            if (
                getattr(config, "n_embd", None) != DIMENSION
                or getattr(config, "num_experts", None) != 8
                or getattr(config, "moe_top_k", None) != 2
            ):
                raise ValueError(
                    "The local model is not the 768-dimensional Nomic v2 MoE architecture"
                )
            config.use_flash_attn = False
            config.fused_bias_fc = False
            config.fused_dropout_add_ln = False
            model_class = get_class_from_dynamic_module(
                f"{CODE_REPOSITORY}--modeling_hf_nomic_bert.NomicBertModel",
                MODEL_ID,
                code_revision=self.code_revision,
                cache_dir=hub,
            )
            with init_empty_weights(include_buffers=False):
                model = model_class(config, add_pooling_layer=False)
            weights = load_file(str(directory / "model.safetensors"), device="cpu")
            if any(
                value.is_floating_point() and value.dtype != torch.float32
                for value in weights.values()
            ):
                raise ValueError("The pinned Nomic model must retain its original float32 weights")
            model.load_state_dict(weights, strict=True, assign=True)
            del weights
            if any(value.is_meta for value in [*model.parameters(), *model.buffers()]):
                raise RuntimeError(
                    "Nomic initialization left parameters or buffers on the meta device"
                )
            model.requires_grad_(False)
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True)
            self._model = model
            self._tokenizer = tokenizer
            try:
                self._encode("research")
            except Exception:
                self._model = None
                self._tokenizer = None
                raise

    def _encode(self, text: str, prefix: str = QUERY_PREFIX) -> list[float]:
        import torch
        import torch.nn.functional as functional

        features = self._tokenizer(
            f"{prefix}{text}",
            padding=True,
            truncation=True,
            max_length=MAX_TOKENS,
            return_tensors="pt",
        )
        features = {name: value.to("cpu") for name, value in features.items()}
        with torch.inference_mode():
            output = self._model(**features)
            hidden = output.last_hidden_state.float()
            if hidden.shape[0] != 1 or hidden.shape[-1] != DIMENSION:
                raise ValueError("Nomic returned an incompatible embedding shape")
            mask = features["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            result = functional.normalize(pooled, p=2, dim=1)[0].tolist()
        norm = math.sqrt(sum(value * value for value in result))
        if (
            len(result) != DIMENSION
            or not all(math.isfinite(value) for value in result)
            or abs(norm - 1) > 1e-4
        ):
            raise ValueError("Nomic did not return a finite unit-length 768-dimensional query")
        return result

    def embed(self, text: str) -> list[float]:
        """Prefix one question with search_query, truncate to 512 tokens and normalize."""
        if not isinstance(text, str):
            raise TypeError("Nomic query text must be a string")
        with self._lock:
            self.load()
            return self._encode(text)

    def encode_document(self, title: str, abstract: str) -> list[float]:
        r"""Encode one published paper only for bounded embedding-space validation.

        The input exactly follows the existing ingestion representation:
        ``search_document: Title: <title>\nAbstract: <abstract>``. This method
        does not replace or rebuild corpus embeddings.
        """
        if not isinstance(title, str) or not isinstance(abstract, str):
            raise TypeError("Nomic document title and abstract must be strings")
        with self._lock:
            self.load()
            return self._encode(f"Title: {title}\nAbstract: {abstract}", DOCUMENT_PREFIX)
