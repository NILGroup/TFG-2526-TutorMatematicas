# backend/scripts/build_dataset.py
from __future__ import annotations

import argparse

import sys
import os

parent_route = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_route)

from ml.dataset.transformer import run_pipeline


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--config", default=None)
    p.add_argument("--split", default="train")
    p.add_argument("--kc-tags-file", required=True)
    p.add_argument("--taxonomy-file", required=True)

    p.add_argument("--phase", choices=["A", "B", "C", "all"], default="all")
    p.add_argument("--max-samples", type=int, default=None)

    p.add_argument("--validate", action="store_true")
    p.add_argument("--validation-rate", type=float, default=1.0)
    p.add_argument("--no-semantic-check", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    args = p.parse_args()

    run_pipeline(
        dataset=args.dataset,
        config=args.config,
        split=args.split,
        kc_tags_file=args.kc_tags_file,
        taxonomy_file=args.taxonomy_file,
        phase=args.phase,
        max_samples=args.max_samples,
        validate=args.validate,
        validation_rate=args.validation_rate,
        no_semantic_check=args.no_semantic_check,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
