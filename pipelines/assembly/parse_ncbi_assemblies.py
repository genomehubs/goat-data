#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Generator
from typing import Optional

import assembly_methods as am
from genomehubs import utils as gh_utils


class Config:
    def __init__(self, config_file, feature_file=None):
        self.config = gh_utils.load_yaml(config_file)
        self.meta = gh_utils.get_metadata(self.config, config_file)
        self.headers = gh_utils.set_headers(self.config)
        self.parse_fns = gh_utils.get_parse_functions(self.config)
        try:
            self.previous_parsed = gh_utils.load_previous(
                self.meta["file_name"], "genbankAccession", self.headers
            )
        except Exception:
            self.previous_parsed = {}
        self.feature_file = feature_file
        if feature_file is not None:
            self.feature_headers = am.set_feature_headers()
            try:
                self.previous_features = gh_utils.load_previous(
                    feature_file, "assembly_id", self.feature_headers
                )
            except Exception:
                self.previous_features = {}


def load_config(config_file: str, feature_file: Optional[str] = None):
    return Config(config_file, feature_file)



def fetch_ncbi_datasets_summary(root_taxid: str):
    taxids = [root_taxid]
    if root_taxid == "2759":
        taxids = [
            "2763",
            "33090",
            "38254",
            "3027",
            "2795258",
            "3004206",
            "2683617",
            "2686027",
            "2698737",
            "2611341",
            "1401294",
            "61964",
            "554915",
            "2611352",
            "2608240",
            "2489521",
            "2598132",
            "2608109",
            "33154",
            "554296",
            "42452",
        ]
    for taxid in taxids:
        command = [
            "datasets",
            "summary",
            "genome",
            "taxon",
            taxid,
            "--as-json-lines",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error fetching datasets summary: {result.stderr}")
            continue
        for line in result.stdout.split("\n"):
            if not line:
                continue
            yield am.convert_keys_to_camel_case(json.loads(line))


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
    if level == "Contig" or level == "Scaffold":
        return
    organelles: defaultdict[str, list] = defaultdict(list)
    try:
        chromosomes: list = []
        assigned_span = 0
        for seq in fetch_ncbi_datasets_sequences(accession, timeout=120):
            if am.is_non_nuclear(seq):
                organelles[seq["chr_name"]].append(seq)
            elif am.is_assigned_to_chromosome(seq):
                assigned_span += seq["length"]
                if am.is_chromosome(seq):
                    chromosomes.append(seq)
    except subprocess.TimeoutExpired:
        print(f"ERROR: Timeout fetching sequence report for {accession}")
        print(chromosomes)
        return
    am.add_organelle_entries(data, organelles)
    am.check_ebp_criteria(data, span, chromosomes, assigned_span)
    am.add_chromosome_entries(data, chromosomes)


def add_report_to_parsed_reports(
    parsed: dict, report: dict, config: Config, biosamples: dict
):
    accession = report["processedAssemblyInfo"]["genbankAccession"]
    row = gh_utils.parse_report_values(config.parse_fns, report)
    if accession not in parsed:
        am.update_organelle_info(report, row)
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
                am.append_to_tsv(
                    config.previous_features[accession],
                    config.feature_headers,
                    {"file_name": config.feature_file},
                )
            parsed[accession] = previous_report
            return True
    return False


def set_up_feature_file(config: Config):
    gh_utils.write_tsv({}, config.feature_headers, {"file_name": config.feature_file})


def append_features(processed_report: dict, config: Config):
    if config.feature_file is not None and "chromosomes" in processed_report:
        am.append_to_tsv(
            processed_report["chromosomes"],
            config.feature_headers,
            {"file_name": config.feature_file},
        )


def set_representative_assemblies(parsed: dict, biosamples: dict):
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
        elif most_recent is not None:
            parsed[most_recent]["biosampleRepresentative"] = 1


def filter_excess_assemblies(parsed: dict, taxon_id: str, threshold: int):
    """Filter out assemblies for a given taxon if the assembly span is below the
    threshold."""

    def is_below_threshold(row):
        return (
            row["taxid"] == taxon_id
            and row["assemblySpan"] is not None
            and row["assemblySpan"] < threshold
        )

    for accession, row in list(parsed.items()):
        if is_below_threshold(row):
            del parsed[accession]


def fetch_and_parse_ncbi_datasets(
    root_taxid: str, config_file: str, feature_file: Optional[str] = None
):
    config = load_config(
        config_file=config_file,
        feature_file=feature_file,
    )
    if feature_file is not None:
        set_up_feature_file(config)
    biosamples = {}
    parsed = {}
    previous_report = {}
    for report in fetch_ncbi_datasets_summary(root_taxid=root_taxid):
        processed_report = process_assembly_report(
            report, previous_report, config, parsed
        )
        if use_previous_report(processed_report, parsed, config):
            continue
        fetch_and_parse_sequence_report(processed_report)
        append_features(processed_report, config)
        add_report_to_parsed_reports(parsed, processed_report, config, biosamples)
        previous_report = processed_report
    set_representative_assemblies(parsed, biosamples)
    filter_excess_assemblies(parsed, taxon_id="9606", threshold=1000000000)
    write_to_tsv(parsed, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and parse NCBI datasets.")
    parser.add_argument(
        "-f",
        "--file_path",
        type=str,
        required=True,
        help="Path to the assembly data files (without extension).",
    )
    parser.add_argument(
        "-r",
        "--root_taxid",
        type=str,
        default="2759",
        help="Root taxonomic ID for fetching datasets (default: 2759).",
    )
    args = parser.parse_args()
    if not args.file_path:
        print("Error: file_path is required.")
        sys.exit(1)

    fetch_and_parse_ncbi_datasets(
        root_taxid=args.root_taxid,
        config_file=f"{args.file_path}.types.yaml",
        feature_file=f"{args.file_path}.features.tsv",
    )
