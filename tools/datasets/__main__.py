"""CPU-only entry point: python -m tools.datasets --help."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .native import (
    PARTITIONS,
    evaluate_bundle,
    generate_bundle,
    outside_repository,
    verify_bundle,
    write_json,
)
from .registry import checksum, load_registry


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["participants"]:
        from .participants import main as participants_main

        return participants_main(argv[1:])
    if argv[:1] == ["frozen-evaluation"]:
        from bouncer.eval.frozen_cli import main as frozen_main

        return frozen_main(argv[1:])
    parser = argparse.ArgumentParser(
        description="Offline dataset provenance and native fixtures; no network or model calls."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("participants", help="Private consent and reviewed-session records.")
    commands.add_parser("frozen-evaluation", help="Private frozen evaluation receipts and reports.")
    generate = commands.add_parser(
        "generate", help="Create new deterministic native synthetic data outside Git."
    )
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--seed", type=int, default=7)
    generate.add_argument("--runs-per-partition", type=int, default=2)
    verify = commands.add_parser(
        "verify", help="Verify checksums, truth coverage and grouped partitions."
    )
    verify.add_argument("--manifest", type=Path, required=True)
    evaluate = commands.add_parser(
        "evaluate", help="Evaluate the existing rules/network baseline without training."
    )
    evaluate.add_argument("--manifest", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--partition", action="append", choices=PARTITIONS)
    evaluate.add_argument("--allow-reserved", action="store_true")
    source = commands.add_parser(
        "check-source", help="Verify an existing local historical file; do not map or train it."
    )
    source.add_argument(
        "--registry", type=Path, default=Path(__file__).with_name("registry.example.json")
    )
    source.add_argument("--dataset-id", required=True)
    source.add_argument("--file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate_bundle(
                args.output, seed=args.seed, runs_per_partition=args.runs_per_partition
            )
            print(json.dumps({"manifest": str(manifest), "synthetic": True, "model_calls": 0}))
        elif args.command == "verify":
            manifest = verify_bundle(args.manifest)
            print(
                json.dumps(
                    {
                        "verified": True,
                        "dataset_id": manifest["dataset_id"],
                        "n_sessions": manifest["n_sessions"],
                        "synthetic": True,
                    }
                )
            )
        elif args.command == "evaluate":
            output = outside_repository(args.output)
            if output.exists():
                raise ValueError("report output already exists; choose a new path")
            report = evaluate_bundle(
                args.manifest, partitions=args.partition, allow_reserved=args.allow_reserved
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            write_json(output, report)
            print(
                json.dumps(
                    {
                        "report": str(output),
                        "synthetic": True,
                        "model_calls": 0,
                        "overall": report["overall"],
                    }
                )
            )
        else:
            registry = load_registry(args.registry)
            entry = next(
                (item for item in registry["datasets"] if item["id"] == args.dataset_id), None
            )
            if entry is None:
                raise ValueError("dataset ID is absent from registry")
            actual = checksum(args.file)
            if actual["sha256"] != entry["sha256"] or actual["bytes"] != entry.get(
                "bytes", actual["bytes"]
            ):
                raise ValueError("historical source checksum mismatch")
            print(
                json.dumps(
                    {
                        "verified": True,
                        "dataset_id": entry["id"],
                        "task": entry["task"],
                        "source_url": entry["source_url"],
                        "native_feature_mapping": entry.get("native_feature_mapping"),
                        "maliciousness_labels": entry.get("maliciousness_labels"),
                        "trained": False,
                    }
                )
            )
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
