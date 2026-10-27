"""Preview by default; --upload explicitly sends the selected result to LangSmith."""

import argparse
import json
import sys
from pathlib import Path

from langsmith import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings
from app.evaluation.langsmith_export import experiment_payload, upload_experiment
from app.evaluation.retrieval_benchmark import MODES, retrieval_experiment_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "result", type=Path, help="Saved evaluation JSON (sanitized or raw)"
    )
    parser.add_argument(
        "--name", required=True, help="Experiment name, e.g. sai-guru-before"
    )
    parser.add_argument(
        "--output", type=Path, default=Path(".local/deployment/langsmith-preview.json")
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Send selected evaluation inputs, references, outputs and metrics",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=MODES,
        help="Export repeat-averaged results of a retrieval ablation instead of an answer evaluation",
    )
    args = parser.parse_args()
    record = json.loads(args.result.read_text(encoding="utf-8"))
    payload = (
        retrieval_experiment_payload(record, args.name, args.retrieval_mode)
        if args.retrieval_mode
        else experiment_payload(record, args.name)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(payload['results'])} cases: {args.output}")
    if not args.upload:
        print(
            "Preview only; no network request made. Add --upload after configuring LANGSMITH_API_KEY."
        )
        return
    cfg = get_settings()
    if not cfg.langsmith_api_key:
        parser.error(
            "LANGSMITH_API_KEY is required for --upload; keep it in your private environment."
        )
    endpoint = cfg.langsmith_endpoint.rstrip("/")
    if not endpoint.startswith("https://"):
        parser.error("Uploads require an HTTPS LangSmith endpoint.")
    client = Client(
        api_url=endpoint,
        api_key=cfg.langsmith_api_key,
        auto_batch_tracing=False,
        hide_inputs=False,
        hide_outputs=False,
    )
    receipt = upload_experiment(client, payload)
    args.output.with_suffix(".receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(
        "Experiment uploaded. Open Datasets & Experiments in your LangSmith workspace."
    )


if __name__ == "__main__":
    main()
