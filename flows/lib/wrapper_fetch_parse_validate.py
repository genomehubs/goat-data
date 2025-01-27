#!/usr/bin/env python3

import contextlib
import os
import sys
from argparse import Action, ArgumentParser, Namespace
from enum import Enum, auto
from glob import glob
from pathlib import Path

file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

with contextlib.suppress(ValueError):
    sys.path.remove(str(parent))

from lib.conditional_import import flow  # noqa: E402
from lib.fetch_previous_file_pair import fetch_previous_file_pair  # noqa: E402
from lib.parse_ncbi_assemblies import parse_ncbi_assemblies  # noqa: E402


class Pipeline(Enum):
    NCBI_ASSEMBLIES = auto()
    REFSEQ_ORGANELLES = auto()
    ETCETERA = auto()


def enum_action(enum_class):
    class EnumAction(Action):
        def __init__(self, *args, **kwargs):
            table = {member.name.casefold(): member for member in enum_class}
            super().__init__(
                *args,
                choices=table,
                **kwargs,
            )
            self.table = table

        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, self.table[values])

    return EnumAction


def parse_ncbi_assemblies_wrapper(
    working_yaml: str, work_dir: str, append: bool
) -> None:
    """
    Wrapper function to parse the NCBI assemblies JSONL file.

    Args:
        working_yaml (str): Path to the working YAML file.
    """
    # use glob to find the jsonl file in the working directory
    glob_path = os.path.join(args.work_dir, "*.jsonl")
    paths = glob(glob_path)
    # raise error if no jsonl file is found
    if not paths:
        raise FileNotFoundError(f"No jsonl file found in {work_dir}")
    # rais error if more than one jsonl file is found
    if len(paths) > 1:
        raise ValueError(f"More than one jsonl file found in {work_dir}")
    parse_ncbi_assemblies(jsonl_path=paths[0], yaml_path=working_yaml, append=append)


@flow()
def fetch_parse_validate(
    pipeline: Pipeline, yaml_path: str, s3_path: str, work_dir: str, append: bool
) -> None:
    """
    Fetch, parse, and validate the TSV file.

    Args:
        pipeline (Pipeline): The pipeline to run.
        args (Namespace): Parsed command-line arguments.
    """
    header_status = fetch_previous_file_pair(
        yaml_path=yaml_path, s3_path=s3_path, work_dir=work_dir
    )
    if not header_status:
        # If the headers do not match, set append == False to parse all records
        append = False
    working_yaml = os.path.join(work_dir, os.path.basename(yaml_path))
    if pipeline == Pipeline.NCBI_ASSEMBLIES:
        parse_ncbi_assemblies_wrapper(
            working_yaml=working_yaml, work_dir=work_dir, append=append
        )
    elif pipeline not in [Pipeline.REFSEQ_ORGANELLES, Pipeline.ETCETERA]:
        raise ValueError("Invalid pipeline.")


def parse_args() -> Namespace:
    """
    Parse command-line arguments.

    Returns:
        Namespace: The parsed arguments.
    """
    parser = ArgumentParser(description="Fetch previous TSV file.")

    parser.add_argument(
        "-p",
        "--pipeline",
        action=enum_action(Pipeline),
        required=True,
        help="Pipeline to run.",
    )
    parser.add_argument(
        "-y",
        "--yaml_path",
        type=str,
        required=True,
        help="Path to the source YAML file.",
    )
    parser.add_argument(
        "-s",
        "--s3_path",
        type=str,
        required=True,
        help="Path to the TSV directory on S3.",
    )
    parser.add_argument(
        "-w",
        "--work_dir",
        type=str,
        default=".",
        help="Path to the working directory (default: current directory).",
    )
    parser.add_argument(
        "-a",
        "--append",
        action="store_true",
        help="Flag to append values to an existing TSV file(s).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()
    fetch_parse_validate(**vars(args))
