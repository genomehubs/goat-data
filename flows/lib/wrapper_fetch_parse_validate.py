#!/usr/bin/env python3

import os
from argparse import Action, ArgumentParser, Namespace
from enum import Enum, auto
from glob import glob

# import boto3
from prefect import flow

from .fetch_previous_file_pair import fetch_previous_file_pair
from .parse_ncbi_assemblies import parse_ncbi_assemblies

# import gzip
# import os
# import shutil

# from prefect.cache_policies import NO_CACHE
# from prefect.events import emit_event

# from . import utils
# from .utils import Config


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


def parse_ncbi_assemblies_wrapper(args: Namespace, working_yaml: str) -> None:
    """
    Wrapper function to parse the NCBI assemblies JSONL file.

    Args:
        args (Namespace): Parsed command-line arguments.
        working_yaml (str): Path to the working YAML file.
    """
    # use glob to find the jsonl file in the working directory
    glob_path = os.path.join(args.work_dir, "*.jsonl")
    paths = glob(glob_path)
    # raise error if no jsonl file is found
    if not paths:
        raise FileNotFoundError(f"No jsonl file found in {args.work_dir}")
    # rais error if more than one jsonl file is found
    if len(paths) > 1:
        raise ValueError(f"More than one jsonl file found in {args.work_dir}")
    parse_ncbi_assemblies(
        jsonl_path=paths[0], yaml_path=working_yaml, append=args.append
    )


@flow()
def fetch_parse_validate(pipeline: Pipeline, args: Namespace) -> None:
    """
    Fetch, parse, and validate the TSV file.

    Args:
        pipeline (Pipeline): The pipeline to run.
        args (Namespace): Parsed command-line arguments.
    """
    fetch_previous_file_pair(
        yaml_path=args.yaml_path, s3_path=args.s3_path, work_dir=args.work_dir
    )
    working_yaml = os.path.join(args.work_dir, os.path.basename(args.yaml_path))
    if pipeline == Pipeline.NCBI_ASSEMBLIES:
        parse_ncbi_assemblies_wrapper(args, working_yaml)
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
        type=bool,
        default=False,
        help="Flag to append values to an existing TSV file(s).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()
    fetch_parse_validate(pipeline=args.pipeline, args=args)
