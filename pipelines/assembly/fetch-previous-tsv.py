#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys

import yaml
from genomehubs import utils as gh_utils
from prefect import flow, task
from prefect.events import emit_event


@task()
def get_filenames(yaml_path: str, remote_path: str) -> tuple:
    """
    Get local and remote filenames from the YAML and remote path.

    Args:
        yaml_path (str): Path to the YAML file.
        remote_path (str): Path to the remote TSV directory.

    Returns:
        tuple: Local and remote filenames.
    """
    try:
        # Get the local filename from the file.name attribute in the YAML
        with open(yaml_path, "r") as f:
            yaml_file = yaml.safe_load(f)
            local_file = yaml_file["file"]["name"]
    except Exception as e:
        # Raise an error if reading the YAML file fails
        raise RuntimeError(f"Error reading YAML file: {e}") from e

    # Get the remote filename from the remote path
    remote_file = os.path.join(remote_path, os.path.basename(local_file))
    return (local_file, remote_file)


@task(retries=2, retry_delay_seconds=2)
def fetch_tsv_file(remote_file: str, local_file: str) -> int:
    """
    Fetch the TSV file from the remote path.

    Args:
        remote_file (str): Path to the remote TSV file.
        local_file (str): Path to the local TSV file.

    Returns:
        int: Number of lines written to the local file.
    """
    # Return 0 if the remote file does not exist
    if subprocess.run(["s3cmd", "info", remote_file]).returncode != 0:
        return 0

    # Fetch the TSV file from the remote path
    command = ["s3cmd", "get", remote_file, local_file]
    result = subprocess.run(command)
    if result.returncode != 0:
        # Raise an error if the command fails
        raise RuntimeError(f"Error fetching TSV file: {result.stderr}")
    # Write to local_file and count lines while writing
    line_count = 0
    with open(local_file, "w") as f:
        for line in result.stdout.splitlines():
            f.write(line + "\n")
            line_count += 1
    return line_count


@task()
def compare_headers(yaml_file: dict, local_file: str) -> bool:
    """
    Compare headers in the local and remote TSV files.

    Args:
        yaml_file (dict): YAML file as a dictionary.
        local_file (str): Path to the local TSV file.

    Returns:
        bool: True if the headers are the same, False otherwise.
    """
    # If local file does not exist, return False
    if not os.path.exists(local_file):
        return False

    # Get the headers from the YAML file
    config = gh_utils.load_yaml(yaml_file)
    headers = gh_utils.set_headers(config)
    try:
        headers = yaml_file["file"]["columns"]
    except Exception as e:
        # Raise an error if reading the YAML file fails
        raise RuntimeError(f"Error reading YAML file: {e}") from e

    # Get the headers from the local TSV file
    with open(local_file, "r") as f:
        local_headers = f.readline().strip().split("\t")

    # Return True if the headers are the same
    return headers == local_headers


@flow()
def fetch_previous_tsv(yaml_path: str, remote_path: str) -> None:
    """
    Fetch the previous TSV file and compare headers.

    Args:
        yaml_path (str): Path to the YAML file.
        remote_path (str): Path to the remote TSV directory.
    """
    (local_file, remote_file) = get_filenames(yaml_path, remote_path)
    line_count = fetch_tsv_file(remote_file, local_file)
    status = compare_headers(yaml_path, local_file)
    emit_event(
        event="fetch.previous.tsv.completed",
        resource={"prefect.resource.id": f"fetch.previous.{yaml_path}"},
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
    args = parser.parse_args()
    if not args.file_path:
        print("Error: file_path is required.", file=sys.stderr)
        sys.exit(1)
    return args


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()

    fetch_previous_tsv(
        yaml_path=args.file_path,
        remote_path=args.remote_path,
    )
