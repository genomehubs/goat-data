#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Generator
from typing import Optional

from genomehubs import utils as gh_utils
from prefect import flow, task
from prefect.runtime.task_run import run_count

from . import utils
from .utils import Config


def parse_assembly_report(jsonl_path: str) -> Generator[dict, None, None]:
    """
    Parses an NCBI datasets JSONL file and yields each assembly report.

    Args:
        jsonl_path (str): The path to the JSONL file.

    Yields:
        dict: The assembly report data as a dictionary.
    """
    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                yield utils.convert_keys_to_camel_case(json.loads(line))
    except Exception as e:
        raise RuntimeError(f"Error reading JSONL file: {e}") from e


def fetch_ncbi_datasets_sequences(
    accession: str, timeout: int = 30
) -> Generator[dict, None, None]:
    """
    Fetches a sequence report from NCBI datasets for the given accession.

    Args:
        accession (str): The accession number to fetch the sequence report for.
        timeout (int): The number of seconds to wait for the command to complete.

    Yields:
        dict: The sequence report data as a JSON object, one line at a time.
    """
    result = subprocess.run(
        [
            "datasets",
            "summary",
            "genome",
            "accession",
            accession,
            "--report",
            "sequence",
            "--as-json-lines",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error fetching sequences report: {result.stderr}")
    for line in result.stdout.split("\n"):
        if not line:
            continue
        yield json.loads(line)


def process_assembly_report(
    report: dict, previous_report: dict, config: Config, parsed: dict
):
    """Process assembly level information.

    This function takes a data dictionary and an optional previous_report dictionary,
    and updates the 'processedAssemblyInfo' field in the data dictionary with
    information about the assembly's RefSeq and GenBank accessions. It also checks if
    the current assembly is the primary assembly based on the 'refseqCategory' field in
    the 'assemblyInfo' dictionary.

    Args:
        report (dict): A dictionary containing the assembly information.
        previous_report (dict, optional): A dictionary containing previous assembly
        information, used to determine if the current assembly is the same as the
        previous one.
        config (Config): A Config object containing the configuration data.
        parsed (dict): A dictionary containing parsed data.

    Returns:
        dict: The updated report dictionary.
    """
    processed_report = {**report, "processedAssemblyInfo": {"organelle": "nucleus"}}
    if "pairedAccession" in report:
        if processed_report["pairedAccession"].startswith("GCF_"):
            processed_report["processedAssemblyInfo"]["refseqAccession"] = report[
                "pairedAccession"
            ]
            processed_report["processedAssemblyInfo"]["genbankAccession"] = report[
                "accession"
            ]
        else:
            processed_report["processedAssemblyInfo"]["refseqAccession"] = report[
                "accession"
            ]
            processed_report["processedAssemblyInfo"]["genbankAccession"] = report[
                "pairedAccession"
            ]
    else:
        processed_report["processedAssemblyInfo"]["genbankAccession"] = report[
            "accession"
        ]
    if (
        previous_report
        and processed_report["processedAssemblyInfo"]["genbankAccession"]
        == previous_report["processedAssemblyInfo"]["genbankAccession"]
    ):
        processed_report = previous_report | processed_report
    if "refseqCategory" in processed_report.get(
        "assemblyInfo", {}
    ) or "refseqAccession" in processed_report.get("processedAssemblyInfo", {}):
        processed_report["processedAssemblyInfo"]["primaryValue"] = 1

    return processed_report


@task()
def write_to_tsv(parsed: dict, config: Config):
    """Write parsed data to a TSV file.

    Args:
        parsed (dict): A dictionary containing parsed data.
        config (Config): A Config object containing the configuration data.
    """
    if config.meta["file_name"].endswith(".gz"):
        config.meta["file_name"] = config.meta["file_name"][:-3]
        gh_utils.write_tsv(parsed, config.headers, config.meta)
        os.system(f"gzip -f {config.meta['file_name']}")
    else:
        gh_utils.write_tsv(parsed, config.headers, config.meta)


@task(log_prints=True, retries=2, retry_delay_seconds=2)
def fetch_and_parse_sequence_report(data: dict):
    """
    Processes the sequence report for an NCBI dataset, adding date fields for assemblies
    that meet certain metrics.

    Args:
        data (dict): A dictionary containing assembly statistics and information.

    Returns:
        None: This function modifies the `data` dictionary in-place to add the processed
            assembly statistics.
    """
    accession = data["accession"]
    span = int(data["assemblyStats"]["totalSequenceLength"])
    level = data["assemblyInfo"]["assemblyLevel"]
    if level in ["Contig", "Scaffold"]:
        return
    organelles: defaultdict[str, list] = defaultdict(list)
    try:
        chromosomes: list = []
        assigned_span = 0
        for seq in fetch_ncbi_datasets_sequences(
            accession, timeout=120 * (run_count + 1)
        ):
            if utils.is_non_nuclear(seq):
                organelles[seq["chr_name"]].append(seq)
            elif utils.is_assigned_to_chromosome(seq):
                assigned_span += seq["length"]
                if utils.is_chromosome(seq):
                    chromosomes.append(seq)
    except subprocess.TimeoutExpired:
        print(f"ERROR: Timeout fetching sequence report for {accession}")
        print(chromosomes)
        return
    utils.add_organelle_entries(data, organelles)
    utils.check_ebp_criteria(data, span, chromosomes, assigned_span)
    utils.add_chromosome_entries(data, chromosomes)


def add_report_to_parsed_reports(
    parsed: dict, report: dict, config: Config, biosamples: dict
):
    """
    Add the report to the parsed reports.

    Args:
        parsed (dict): A dictionary containing parsed data.
        report (dict): A dictionary containing the assembly report.
        config (Config): A Config object containing the configuration data.
        biosamples (dict): A dictionary containing biosample information.
    """
    accession = report["processedAssemblyInfo"]["genbankAccession"]
    row = gh_utils.parse_report_values(config.parse_fns, report)
    if accession not in parsed:
        utils.update_organelle_info(report, row)
    if "linkedAssembly" not in row or row["linkedAssembly"] is None:
        row["linkedAssembly"] = []
    biosample = row.get("biosampleAccession", [])
    if biosample not in biosamples:
        biosamples[biosample] = []
    if biosample:
        linked_assemblies = biosamples[biosample]
        for acc in linked_assemblies:
            if acc == accession:
                continue
            linked_row = parsed[acc]
            if accession not in linked_row["linkedAssembly"]:
                linked_row["linkedAssembly"].append(accession)
            if acc not in row["linkedAssembly"]:
                row["linkedAssembly"].append(acc)
        linked_assemblies.append(accession)
    parsed[accession] = row
    return parsed


def use_previous_report(processed_report: dict, parsed: dict, config: Config):
    """
    Use the previous report if the current report is the same as the previous one.

    Args:
        processed_report (dict): A dictionary containing processed assembly data.
        parsed (dict): A dictionary containing parsed data.
        config (Config): A Config object containing the configuration data.
    """
    accession = processed_report["processedAssemblyInfo"]["genbankAccession"]
    if accession in config.previous_parsed:
        previous_report = config.previous_parsed[accession]
        if (
            processed_report["assemblyInfo"]["releaseDate"]
            == previous_report["releaseDate"]
        ):
            if (
                config.feature_file is not None
                and accession in config.previous_features
                and accession not in parsed
            ):
                utils.append_to_tsv(
                    config.previous_features[accession],
                    config.feature_headers,
                    {"file_name": config.feature_file},
                )
            parsed[accession] = previous_report
            return True
    return False


@task()
def set_up_feature_file(config: Config):
    """
    Set up the feature file.

    Args:
        config (Config): A Config object containing the configuration data.
    """
    gh_utils.write_tsv({}, config.feature_headers, {"file_name": config.feature_file})


def append_features(processed_report: dict, config: Config):
    """
    Append features to the feature file.

    Args:
        processed_report (dict): A dictionary containing processed assembly data.
        config (Config): A Config object containing the configuration data.
    """
    if config.feature_file is not None and "chromosomes" in processed_report:
        utils.append_to_tsv(
            processed_report["chromosomes"],
            config.feature_headers,
            {"file_name": config.feature_file},
        )


@task(log_prints=True)
def set_representative_assemblies(parsed: dict, biosamples: dict):
    """
    Set the representative assembly for each biosample.

    Args:
        parsed (dict): A dictionary containing parsed data.
        biosamples (dict): A dictionary containing biosample information.
    """
    for accessions in biosamples.values():
        most_recent = None
        primary_assembly = None
        latest_date = None
        for accession in accessions:
            if accession not in parsed:
                continue
            row = parsed[accession]
            if most_recent is None or row["releaseDate"] > latest_date:
                most_recent = accession
                latest_date = row["releaseDate"]
            if row["refseqCategory"] is not None:
                primary_assembly = accession
        if primary_assembly is not None:
            parsed[primary_assembly]["biosampleRepresentative"] = 1
        else:
            parsed[most_recent]["biosampleRepresentative"] = 1


@task()
def process_assembly_reports(
    jsonl_path: str,
    config: Config,
    biosamples: dict,
    parsed: dict,
    previous_report: dict,
):
    """
    Process assembly reports and fetch sequence reports.

    Args:
        jsonl_path (str): Path to the NCBI datasets JSONL file.
        config (Config): A Config object containing the configuration data.
        biosamples (dict): A dictionary containing biosample information.
        parsed (dict): A dictionary containing parsed data.
        previous_report (dict): A dictionary containing the previous assembly report.

    Returns:
        None
    """
    for report in parse_assembly_report(jsonl_path=jsonl_path):
        processed_report = process_assembly_report(
            report, previous_report, config, parsed
        )
        if use_previous_report(processed_report, parsed, config):
            continue
        fetch_and_parse_sequence_report(processed_report)
        append_features(processed_report, config)
        add_report_to_parsed_reports(parsed, processed_report, config, biosamples)
        previous_report = processed_report


@flow(log_prints=True)
def parse_ncbi_assemblies(
    jsonl_path: str, yaml_path: str, feature_file: Optional[str] = None
):
    """
    Parse NCBI datasets assembly data.

    Args:
        jsonl_path (str): Path to the NCBI datasets JSONL file.
        yaml_path (str): Path to the YAML configuration file.
        feature_file (str): Path to the feature file.
    """
    config = utils.load_config(
        config_file=yaml_path,
        feature_file=feature_file,
    )
    if feature_file is not None:
        set_up_feature_file(config)
    biosamples = {}
    parsed = {}
    previous_report = {}
    process_assembly_reports(jsonl_path, config, biosamples, parsed, previous_report)
    set_representative_assemblies(parsed, biosamples)
    write_to_tsv(parsed, config)


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
    # parser.add_argument(
    #     "-f",
    #     "--features",
    #     type=str,
    #     default=False,
    #     help="Flag to save chromosomes as features to a TSV file.",
    # )
    parser.add_argument(
        "-a",
        "--append",
        type=bool,
        default=False,
        help="Flag to append values to an existing TSV file(s).",
    )

    args = parser.parse_args()

    if not args.jsonl_path:
        print("Error: jsonl_path is required.")
        sys.exit(1)

    if not args.file_stem:
        print("Error: file_stem is required.")
        sys.exit(1)
    return args


if __name__ == "__main__":
    args = parse_args()

    parse_ncbi_assemblies(
        jsonl_path=args.jsonl_path,
        yaml_path=f"{args.file_stem}.types.yaml",
        feature_file=f"{args.file_stem}.features.tsv",
    )
