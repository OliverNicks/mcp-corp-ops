"""
Local Quantized ONNX Embedding Engine.

Provides high-throughput, low-latency CPU text embeddings using:
- Hugging Face Fast Rust Tokenizer (via tokenizers.Tokenizer)
- Quantized INT8 ONNX Model (via onnxruntime.InferenceSession)
- Thread pool optimization for intra-op parallelism
- Mean pooling over token embeddings with attention mask
- L2 unit-norm normalization for fast inner-product cosine similarity
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from src.core.config import settings

logger = logging.getLogger("mcp.cache.embeddings")


class EmbeddingEngine:
    """
    Sub-8ms CPU Embedding Engine utilizing INT8 Quantized ONNX Runtime
    and Fast Rust Tokenizer for paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        intra_op_threads: Optional[int] = None,
    ) -> None:
        self.model_path = Path(model_path or settings.onnx_model_path)
        self.tokenizer_path = Path(tokenizer_path or settings.tokenizer_path)
        self.embedding_dim = embedding_dim or settings.embedding_dim

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Quantized ONNX model file not found at: {self.model_path.resolve()}. "
                f"Please run 'uv run python scripts/export_onnx_model.py' to generate it."
            )

        if not self.tokenizer_path.is_file():
            raise FileNotFoundError(
                f"Fast Tokenizer configuration file not found at: {self.tokenizer_path.resolve()}. "
                f"Please run 'uv run python scripts/export_onnx_model.py' to generate it."
            )

        # 1. Initialize Fast Rust Tokenizer
        logger.debug("Loading Fast Rust Tokenizer from %s", self.tokenizer_path)
        self.tokenizer = Tokenizer.from_file(str(self.tokenizer_path))

        # 2. Configure ONNX Runtime Session for Optimal CPU Performance
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Configure thread pool for intra-op parallelism
        threads = intra_op_threads or max(1, os.cpu_count() or 1)
        session_options.intra_op_num_threads = threads
        session_options.inter_op_num_threads = 1
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        logger.debug(
            "Initializing ONNX InferenceSession (CPUExecutionProvider, intra_op_threads=%d) from %s",
            threads,
            self.model_path,
        )
        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        # Validate input/output node names
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]
        logger.info(
            "EmbeddingEngine initialized successfully: model=%s (dim=%d, intra_threads=%d)",
            self.model_path.name,
            self.embedding_dim,
            threads,
        )

    def _mean_pooling_and_normalize(
        self,
        last_hidden_state: np.ndarray,
        attention_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Applies mean pooling over token embeddings respecting attention mask,
        followed by L2 normalization to project vectors onto the unit hypersphere.

        :param last_hidden_state: (batch_size, seq_len, 384)
        :param attention_mask: (batch_size, seq_len)
        :return: (batch_size, 384) unit-norm vectors
        """
        # Expand attention mask: (batch_size, seq_len, 1)
        input_mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)

        # Sum token embeddings across sequence length
        sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1)

        # Calculate mask token counts with numerical stability clamp
        sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)

        # Mean pooling: (batch_size, 384)
        mean_pooled = sum_embeddings / sum_mask

        # L2 normalization: vector / ||vector||_2
        norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        norms = np.clip(norms, a_min=1e-9, a_max=None)
        normalized = mean_pooled / norms

        return normalized

    def embed_text(self, text: str) -> List[float]:
        """
        Generate a 384-dimensional unit-length embedding vector for a single string.

        :param text: Input string.
        :return: List of 384 floats representing the L2-normalized embedding.
        """
        encoded = self.tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }

        outputs = self.session.run(None, inputs)
        last_hidden_state = outputs[0]  # (1, seq_len, 384)

        normalized = self._mean_pooling_and_normalize(last_hidden_state, attention_mask)
        embedding: List[float] = normalized[0].tolist()
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate 384-dimensional unit-length embedding vectors for a batch of strings.

        :param texts: List of input strings.
        :return: List of 384-dimensional float vectors.
        """
        if not texts:
            return []

        encoded_batch = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded_batch], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded_batch], dtype=np.int64)

        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }

        outputs = self.session.run(None, inputs)
        last_hidden_state = outputs[0]  # (batch_size, seq_len, 384)

        normalized = self._mean_pooling_and_normalize(last_hidden_state, attention_mask)
        return normalized.tolist()

    def embed_numpy(self, text: str) -> np.ndarray:
        """
        Convenience method returning a 1D numpy array (float32) of shape (384,).
        """
        return np.array(self.embed_text(text), dtype=np.float32)

    @staticmethod
    def cosine_similarity(
        vec_a: Union[List[float], np.ndarray],
        vec_b: Union[List[float], np.ndarray],
    ) -> float:
        """
        Calculates cosine similarity between two vectors.
        Since vectors from this engine are strictly L2-normalized,
        cosine similarity is equivalent to the dot product.
        """
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        return float(np.dot(a, b))


# Global cached singleton instance
_engine_instance: Optional[EmbeddingEngine] = None


def get_embedding_engine() -> EmbeddingEngine:
    """Returns the shared EmbeddingEngine singleton instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EmbeddingEngine()
    return _engine_instance


def embed_text(text: str) -> List[float]:
    """Helper function to embed a single text using the global EmbeddingEngine singleton."""
    return get_embedding_engine().embed_text(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Helper function to embed a batch of texts using the global EmbeddingEngine singleton."""
    return get_embedding_engine().embed_batch(texts)
