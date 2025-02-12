#!/usr/bin/env python3

import contextlib
import sys
from pathlib import Path

file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

with contextlib.suppress(ValueError):
    sys.path.remove(str(parent))

from lib.utils import Parser  # noqa: E402
from parsers.args import parse_args  # noqa: E402


def parse_refseq_organelles(working_yaml: str, work_dir: str, append: bool) -> None:
    """
    Wrapper function to parse the RefSeq organelles JSONL file.

    Args:
        working_yaml (str): Path to the working YAML file.
        work_dir (str): Path to the working directory.
        append (bool): Whether to append to the existing TSV file.
    """
    print("parsing RefSeq organelles files")


def plugin():
    """Register the flow."""
    return Parser(
        name="REFSEQ_ORGANELLES",
        func=parse_refseq_organelles,
        description="Parse the RefSeq organelles files in a directory.",
    )


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()
    parse_refseq_organelles(**vars(args))
