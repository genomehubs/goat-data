#!/usr/bin/env python3

"""
Prefect flow of flows wrapper around assembly/update-ncbi-datasets.py
and general/fetch-previous-tsv.py.
"""

import argparse
import os
import sys

from prefect import Flow, task
from prefect.engine.executors import DaskExecutor

from flows.assembly.update_ncbi_datasets import fetch_ncbi_datasets_summary
from flows.general.fetch_previous_tsv import fetch_tsv_file, get_filenames

@task
def print_success():
    print("Flow completed successfully.")

with Flow("NCBI Datasets") as flow:
    # Get local and remote filenames from the YAML and remote path
    yaml_path = "data/genomehubs.yaml"
    remote_path = "s3://genomehubs/ncbi-datasets"
    work_dir = "data"
    local_file, remote_file = get_filenames(yaml_path, remote_path, work_dir)

    # Fetch the TSV file from the remote path using boto3
    fetch_tsv_file(remote_file, local_file)

    # Fetch NCBI datasets summary for a given root taxID
    root_taxid = "2759"
    file_path = os.path.join(work_dir, "ncbi-datasets-summary.json")
    fetch_ncbi_datasets_summary(root_taxid, file_path)

    # Print success message
    print_success()

# Execute the flow
executor = DaskExecutor(address="tcp://
executor.start()
flow.run(executor=executor)
executor.shutdown()

