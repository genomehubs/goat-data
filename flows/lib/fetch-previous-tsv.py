#!/usr/bin/env python3

import argparse
import gzip
import os
import shutil

import boto3
from prefect import flow, task
from prefect.events import emit_event

from . import utils
from .utils import Config


@task()
def get_filenames(config: Config, remote_path: str, work_dir: str) -> tuple:
    """
    Get local and remote filenames from the YAML and remote path.

    Args:
        config (Config): YAML file as a dictionary.
        remote_path (str): Path to the remote TSV directory.
        work_dir (str): Path to the working directory.

    Returns:
        tuple: Local and remote filenames.
    """
    try:
        # Get the local filename from the config.file.name attribute
        local_file = config.config["file"]["name"]
    except Exception as e:
        # Raise an error if reading the YAML file fails
        raise RuntimeError("Error reading file name from config") from e

    # Append the working directory to the local filename
    local_file = os.path.join(work_dir, local_file)

    # Get the remote filename from the remote path
    remote_file = os.path.join(remote_path, os.path.basename(local_file))
    return (local_file, remote_file)


@task(retries=2, retry_delay_seconds=2)
def fetch_tsv_file(remote_file: str, local_file: str) -> int:
    """
    Fetch the TSV file from the remote path using boto3.

    Args:
        remote_file (str): Path to the remote TSV file.
        local_file (str): Path to the local TSV file.

    Returns:
        int: Number of lines written to the local file.
    """
    s3 = boto3.client("s3")
    bucket_name, key = remote_file.replace("s3://", "").split("/", 1)

    try:
        s3.head_object(Bucket=bucket_name, Key=key)
    except s3.exceptions.ClientError:
        return 0

    # fetch the file
    os.makedirs(os.path.dirname(local_file), exist_ok=True)
    with open(local_file, "wb") as f:
        s3.download_fileobj(bucket_name, key, f)

    # Check if the file is gzipped
    if local_file.endswith(".gz"):
        with gzip.open(local_file, "rt") as f:
            line_count = sum(1 for _ in f)
    else:
        with open(local_file, "r") as f:
            line_count = sum(1 for _ in f)

    return line_count


@task()
def compare_headers(config: utils.Config, local_file: str) -> bool:
    """
    Compare headers in the local and remote TSV files.

    Args:
        config (Config): YAML file as a dictionary.
        local_file (str): Path to the local TSV file.

    Returns:
        bool: True if the headers are the same, False otherwise.
    """
    # If local file does not exist, return False
    if not os.path.exists(local_file):
        return False

    # Get the headers from the local TSV file
    if local_file.endswith(".gz"):
        with gzip.open(local_file, "rt") as f:
            local_headers = f.readline().strip().split("\t")
    else:
        with open(local_file, "r") as f:
            local_headers = f.readline().strip().split("\t")

    # Return True if the headers are the same
    return config.headers == local_headers


@task()
def copy_yaml_files(yaml_path: str, config: utils.Config, work_dir: str) -> None:
    """
    Copy the YAML files to the working directory.

    Args:
        yaml_path (str): Path to the YAML file.
        config (Config): YAML file as a dictionary.
        work_dir (str): Path to the working directory.
    """
    # Copy the file at yaml_path to the working directory
    shutil.copy(yaml_path, work_dir)

    # Copy any dependencies to the working directory
    if "needs" in config.config["file"]:
        source_dir = os.path.dirname(yaml_path)
        for file in config.config["file"]["needs"]:
            file_path = os.path.join(source_dir, file)
            shutil.copy(file_path, work_dir)


@flow()
def fetch_previous_tsv(yaml_path: str, remote_path: str, work_dir: str) -> None:
    """
    Fetch the previous TSV file and compare headers.

    Args:
        yaml_path (str): Path to the YAML file.
        remote_path (str): Path to the remote TSV directory.
        work_dir (str): Path to the working directory.
    """
    config = utils.load_config(yaml_path)
    (local_file, remote_file) = get_filenames(config, remote_path, work_dir)
    line_count = fetch_tsv_file(remote_file, local_file)
    copy_yaml_files(yaml_path, config, work_dir)
    status = compare_headers(config, local_file)
    emit_event(
        event="fetch.previous.tsv.completed",
        resource={
            "prefect.resource.id": f"fetch.previous.{yaml_path}",
            "prefect.resource.type": "fetch.previous",
            "prefect.resource.matches.previous": "yes" if status else "no",
        },
        payload={"line_count": line_count, "headers_match": status},
    )
    return status


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Fetch previous TSV file.")

    parser.add_argument(
        "-y",
        "--yaml_path",
        type=str,
        required=True,
        help="Path to the local YAML file.",
    )
    parser.add_argument(
        "-p",
        "--remote_path",
        type=str,
        required=True,
        help="Path to the remote TSV directory.",
    )
    parser.add_argument(
        "-w",
        "--work_dir",
        type=str,
        default=".",
        help="Path to the working directory (default: current directory).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()

    fetch_previous_tsv(
        yaml_path=args.yaml_path,
        remote_path=args.remote_path,
        work_dir=args.work_dir,
    )
