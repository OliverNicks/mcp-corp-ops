"""
Export and Quantize Sentence-Transformer Model to ONNX Dynamic INT8.

Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions)
Outputs:
  - models/embedding_quantized.onnx: INT8 quantized CPU-optimized model (<120MB)
  - models/tokenizer.json: HuggingFace Fast Rust tokenizer for zero-dependency inference
"""

import argparse
import logging
import os
from pathlib import Path
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("export_onnx")


def export_and_quantize(
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    output_dir: str = "models",
    keep_fp32: bool = False,
) -> None:
    """
    Downloads model from HuggingFace, exports PyTorch graph to ONNX with dynamic axes,
    applies dynamic INT8 quantization for sub-8ms CPU inference, and saves the fast tokenizer.
    """
    # 0. Check dependencies
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        logger.error(
            "Missing export dependencies (torch, transformers). "
            "Please install them via: uv pip install '.[export]' or uv pip install torch transformers onnx"
        )
        raise SystemExit(1) from exc

    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as exc:
        logger.error("Missing onnxruntime. Install via: uv pip install onnxruntime")
        raise SystemExit(1) from exc

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    fp32_onnx_path = out_path / "embedding_fp32.onnx"
    quantized_onnx_path = out_path / "embedding_quantized.onnx"
    tokenizer_json_path = out_path / "tokenizer.json"

    logger.info("==================================================================")
    logger.info("Step 1: Downloading HuggingFace model & tokenizer: %s", model_name)
    logger.info("==================================================================")
    start_dl = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    logger.info("Downloaded model and tokenizer in %.2fs", time.perf_counter() - start_dl)

    # Save Fast Rust Tokenizer
    logger.info("Saving Fast Tokenizer JSON to: %s", tokenizer_json_path)
    tokenizer.backend_tokenizer.save(str(tokenizer_json_path))

    # 2. Export PyTorch graph to FP32 ONNX
    logger.info("==================================================================")
    logger.info("Step 2: Exporting PyTorch graph to ONNX: %s", fp32_onnx_path)
    logger.info("==================================================================")
    start_export = time.perf_counter()

    class EmbeddingModelWrapper(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            return self.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state

    wrapped_model = EmbeddingModelWrapper(model)

    dummy_sentence = "Huppa Avery winter overall waterproof membrane 10000mm"
    dummy_input = tokenizer(
        dummy_sentence,
        padding=True,
        truncation=True,
        return_tensors="pt",
    )

    input_names = ["input_ids", "attention_mask"]
    input_tuple = (dummy_input["input_ids"], dummy_input["attention_mask"])

    dynamic_axes = {
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "last_hidden_state": {0: "batch_size", 1: "sequence_length"},
    }

    torch.onnx.export(
        wrapped_model,
        input_tuple,
        f=str(fp32_onnx_path),
        input_names=input_names,
        output_names=["last_hidden_state"],
        dynamic_axes=dynamic_axes,
        opset_version=14,
        do_constant_folding=True,
        dynamo=False,
    )
    fp32_size_mb = fp32_onnx_path.stat().st_size / (1024 * 1024)
    logger.info(
        "Exported FP32 ONNX model (%.1f MB) in %.2fs",
        fp32_size_mb,
        time.perf_counter() - start_export,
    )

    # 3. Dynamic INT8 Quantization (CPU Optimized)
    logger.info("==================================================================")
    logger.info("Step 3: Applying Dynamic INT8 Quantization: %s", quantized_onnx_path)
    logger.info("==================================================================")
    start_quant = time.perf_counter()

    quantize_dynamic(
        model_input=str(fp32_onnx_path),
        model_output=str(quantized_onnx_path),
        weight_type=QuantType.QInt8,
        per_channel=False,
        reduce_range=False,
    )

    int8_size_mb = quantized_onnx_path.stat().st_size / (1024 * 1024)
    compression_ratio = (1.0 - (int8_size_mb / fp32_size_mb)) * 100
    logger.info(
        "Quantized model generated: %.1f MB (%.1f%% reduction from %.1f MB) in %.2fs",
        int8_size_mb,
        compression_ratio,
        fp32_size_mb,
        time.perf_counter() - start_quant,
    )

    # Remove temporary FP32 ONNX model unless explicitly retained
    if not keep_fp32:
        logger.info("Cleaning up intermediate FP32 model: %s", fp32_onnx_path)
        fp32_onnx_path.unlink(missing_ok=True)

    # 4. Self-Verification of Exported Model & Latency
    logger.info("==================================================================")
    logger.info("Step 4: Self-Verification of Quantized Model on CPU")
    logger.info("==================================================================")
    verify_quantized_model(quantized_onnx_path, tokenizer_json_path)


def verify_quantized_model(model_path: Path, tokenizer_path: Path) -> None:
    """Runs a benchmark inference with the exported assets and asserts 384 dimensions."""
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    # Load Fast Tokenizer
    tok = Tokenizer.from_file(str(tokenizer_path))

    # Configure CPU Execution Provider session
    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session_options.intra_op_num_threads = max(1, os.cpu_count() or 1)

    session = ort.InferenceSession(
        str(model_path),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )

    test_sentence = "Комбінезон зимовий Huppa Avery (300г) теплий мембранний"
    encoded = tok.encode(test_sentence)

    inputs = {
        "input_ids": np.array([encoded.ids], dtype=np.int64),
        "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
    }

    # Warmup
    _ = session.run(None, inputs)

    # Latency benchmark
    latencies = []
    for _ in range(10):
        t0 = time.perf_counter()
        outputs = session.run(None, inputs)
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    last_hidden_state = outputs[0]  # shape: (1, seq_len, 384)

    # Mean pooling
    mask = np.array([encoded.attention_mask], dtype=np.float32)[:, :, np.newaxis]
    sum_embeddings = np.sum(last_hidden_state * mask, axis=1)
    sum_mask = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
    mean_pooled = sum_embeddings / sum_mask

    # L2 normalize
    norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
    norm = np.clip(norm, a_min=1e-9, a_max=None)
    embedding = (mean_pooled / norm)[0]

    dim = len(embedding)
    logger.info("Verification Succeeded:")
    logger.info("  - Embedding Dimension: %d (Expected: 384)", dim)
    logger.info("  - CPU Inference Latency (avg over 10 runs): %.2f ms", avg_latency)

    assert dim == 384, f"Expected 384 dimensions, got {dim}"
    if avg_latency < 8.0:
        logger.info("  - SLA Met: %.2f ms < 8.0 ms CPU SLA target", avg_latency)
    else:
        logger.warning("  - Note: Latency %.2f ms (hardware dependent)", avg_latency)

    logger.info("Export & Verification Complete! Models ready in 'models/'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and Quantize HF Model to ONNX INT8")
    parser.add_argument(
        "--model-name",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="HuggingFace repository ID or local path",
    )
    parser.add_argument(
        "--output-dir",
        default="models",
        help="Directory to save quantized model and tokenizer",
    )
    parser.add_argument(
        "--keep-fp32",
        action="store_true",
        help="Keep unquantized FP32 ONNX model alongside INT8 model",
    )
    args = parser.parse_args()

    export_and_quantize(
        model_name=args.model_name,
        output_dir=args.output_dir,
        keep_fp32=args.keep_fp32,
    )


if __name__ == "__main__":
    main()
