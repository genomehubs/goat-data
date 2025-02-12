#!/usr/bin/env python3

import argparse


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Fetch and parse NCBI datasets.")
    parser.add_argument(
        "-j",
        "--jsonl_path",
        type=str,
        required=True,
        help="Path to the NCBI datasets JSONL file.",
    )
    parser.add_argument(
        "-y",
        "--yaml_path",
        type=str,
        required=True,
        help="Path to the YAML file.",
    )
    parser.add_argument(
        "-a",
        "--append",
        action="store_true",
        help="Flag to append values to an existing TSV file(s).",
    )

    return parser.parse_args()
