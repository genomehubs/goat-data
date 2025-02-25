#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys

from prefect import flow, task


@task(retries=2, retry_delay_seconds=2)
def fetch_ncbi_datasets_summary(
    root_taxid: str,
    file_path: str,
    min_lines: int = 1,
) -> int:
    """
    Fetch NCBI datasets summary for a given root taxID.

    Args:
        file_path (str): Path to the output file.
        root_taxid (str): Root taxonomic ID for fetching datasets.
        min_lines (int): Minimum number of lines in the output file.

    Returns:
        int: Number of lines written to the output file.
    """

    # Fetch datasets summary for the root taxID
    command = [
        "datasets",
        "summary",
        "genome",
        "taxon",
        root_taxid,
        "--as-json-lines",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        # Raise an error if the command fails
        raise RuntimeError(f"Error fetching datasets summary: {result.stderr}")

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # Write to the file and count lines while writing
        line_count = 0
        with open(file_path, "w") as f:
            for line in result.stdout.splitlines():
                f.write(line + "\n")
                line_count += 1

        # Check if the file has at least 10000 lines
        if line_count < min_lines:
            raise RuntimeError(
                f"File {file_path} has less than {min_lines} lines: {line_count}"
            )
    except Exception as e:
        # Raise an error if writing to the file fails
        raise RuntimeError(f"Error writing datasets summary to file: {e}") from e

    # Return the number of lines written to the file
    return line_count


@task(retries=2, retry_delay_seconds=2)
def compare_datasets_summary(local_path: str, remote_path: str) -> bool:
    """
    Compare local and remote NCBI datasets summary files.

    Args:
        local_path (str): Path to the local file.
        remote_path (str): Path to the remote file.

    Returns:
        bool: True if the files are the same, False otherwise.
    """

    # Return error if the local file does not exist
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file {local_path} does not exist")

    # Return false if the remote file does not exist
    if subprocess.run(["s3cmd", "info", remote_path]).returncode != 0:
        return False

    # Generate md5sum of the local file
    local_md5 = subprocess.run(
        ["md5sum", local_path], capture_output=True, text=True
    ).stdout.split()[0]

    # Generate md5sum of the remote file
    remote_md5 = (
        subprocess.run(["s3cmd", "info", remote_path], capture_output=True, text=True)
        .stdout.splitlines()[1]
        .split()[1]
    )

    # Return True if the md5sums are the same
    return local_md5 == remote_md5


@flow()
def fetch_ncbi_datasets(root_taxid: str, file_path: str, remote_path: str) -> None:
    fetch_ncbi_datasets_summary(root_taxid, file_path)
    return compare_datasets_summary(file_path, remote_path)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Fetch and parse NCBI datasets.")
    parser.add_argument(
        "-r",
        "--root_taxid",
        type=str,
        default="2759",
        help="Root taxonomic ID for fetching datasets (default: 2759).",
    )
    parser.add_argument(
        "-f",
        "--file_path",
        type=str,
        required=True,
        help="Path to the NCBI datasets JSONL file.",
    )
    parser.add_argument(
        "-p",
        "--remote_path",
        type=str,
        required=True,
        help="Path to the remote NCBI datasets JSONL file.",
    )
    args = parser.parse_args()
    if not args.file_path:
        print("Error: file_path is required.", file=sys.stderr)
        sys.exit(1)
    return args


if __name__ == "__main__":
    """Run the flow."""
    args = parse_args()

    fetch_ncbi_datasets(
        root_taxid=args.root_taxid,
        file_path=args.file_path,
        remote_path=args.remote_path,
    )
