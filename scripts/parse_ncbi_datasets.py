#!/usr/bin/env python
"""
This script parses NCBI dataset files in JSONL format and outputs summary data in TSV
format based on a provided configuration.

It takes the following arguments:

- -f/--file: The path to the JSONL input file to parse,
    e.g.: '/path/to/ncbi_dataset/data/assembly_data_report.jsonl'.

- -c/--config: The path to the configuration file specifying which fields
    to output, e.g.: '/path/to/output/ncbi_datasets_eukaryota.types.yaml'.

- --features: A file path to output processed features. If not provided, the script
    will not process features.

The script parses the JSONL file, extracting fields based on the provided
configuration. It then processes the data, adding additional fields based on the
associated sequence report. If a previous TSV file is available at the output file
location, as specified in the configuration file, the script will load
the previous data and update entries only if the release date has changed.

Each dataset contains only the fields defined in the configuration file. Additional
fields can be included by adding entries with both `header` and `path` keys to the
configuration file.
"""


import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Generator
from typing import Optional

from genomehubs import utils as gh_utils


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments for the NCBI dataset parsing script.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--file",
        default="ncbi_test/ncbi_dataset/data/assembly_data_report.jsonl",
        help="path to jsonl file",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="ncbi_test/ncbi_datasets_eukaryota.types.yaml",
        help="path to config file",
    )
    parser.add_argument(
        "--features",
        default=None,
        help="path to output features",
    )
    return parser.parse_args()


def fetch_sequences_report(accession: str) -> Generator[dict, None, None]:
    """
    Fetches a sequence report from NCBI datasets for the given accession.

    Args:
        accession (str): The accession number to fetch the sequence report for.

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
        stdout=subprocess.PIPE,
        timeout=30,
    )
    for line in result.stdout.decode("utf-8").split("\n"):
        if not line:
            continue
        yield json.loads(line)


def set_organelle_name(seq: dict) -> Optional[str]:
    """
    Determines the organelle type (mitochondrion or plastid) based on the assigned
    molecule location type in the provided sequence data.

    Args:
        seq (dict): A dictionary containing sequence data, including the
            "assigned_molecule_location_type" field.

    Returns:
        Optional[str]: The organelle type, either "mitochondrion" or "plastid", or None
            if key error.
    """
    try:
        return (
            "mitochondrion"
            if seq[0]["assigned_molecule_location_type"].casefold()
            == "Mitochondrion".casefold()
            else "plastid"
        )
    except KeyError:
        return None


def is_assembled_molecule(seq: dict) -> bool:
    """
    Determines if the provided sequence data represents an assembled molecule.

    Args:
        seq (dict): A dictionary containing sequence data, including the "role" field.

    Returns:
        bool: True if the sequence data represents an assembled molecule, False
            otherwise.
    """
    try:
        return seq[0]["role"] == "assembled-molecule"
    except (IndexError, KeyError):
        return False


def set_additional_organelle_values(
    seq: dict, organelle: dict, data: dict, organelle_name: str
) -> None:
    """
    Sets additional organelle-related values in the provided data dictionary based on
    the sequence data. If the sequence data represents an assembled molecule, it
    extracts the GenBank accession, total sequence length, and GC percentage, and
    stores these values in the `processedOrganelleInfo` dictionary. If the sequence
    data does not represent an assembled molecule, it stores the accession numbers of
    the individual scaffolds in the `processedOrganelleInfo` dictionary.

    Args:
        seq (dict): A dictionary containing sequence data.
        organelle (dict): A dictionary representing an organelle.
        data (dict): A dictionary containing processed data.
        organelle_name (str): The name of the organelle.
    """
    if is_assembled_molecule(seq):
        organelle["genbankAssmAccession"] = seq[0]["genbank_accession"]
        organelle["totalSequenceLength"] = seq[0]["length"]
        organelle["gcPercent"] = seq[0]["gc_percent"]
        data["processedOrganelleInfo"][organelle_name]["assemblySpan"] = organelle[
            "totalSequenceLength"
        ]
        data["processedOrganelleInfo"][organelle_name]["gcPercent"] = organelle[
            "gcPercent"
        ]
        data["processedOrganelleInfo"][organelle_name]["accession"] = seq[0][
            "genbank_accession"
        ]
    else:
        data["processedOrganelleInfo"][organelle_name]["scaffolds"] = ";".join(
            [entry["genbank_accession"] for entry in seq]
        )


def initialise_organelle_info(data: dict, organelle_name: str):
    """
    Initializes the `processedOrganelleInfo` dictionary in the provided `data`
    dictionary, creating a new entry for the specified `organelle_name` if it doesn't
    already exist.

    Args:
        data (dict): The dictionary containing the processed data.
        organelle_name (str): The name of the organelle.
    """
    if "processedOrganelleInfo" not in data:
        data["processedOrganelleInfo"] = {}
    if organelle_name not in data["processedOrganelleInfo"]:
        data["processedOrganelleInfo"][organelle_name] = {}


def set_organelle_values(data: dict, seq: dict) -> dict:
    """
    Sets organelle-related values in the provided data dictionary based on the sequence
    report data.

    Args:
        data (dict): A dictionary containing processed data.
        seq (dict): A dictionary containing sequence data.

    Returns:
        dict: A dictionary containing organelle-related information.
    """
    organelle: dict = {
        "sourceAccession": data["accession"],
        "organelle": seq[0]["assigned_molecule_location_type"],
    }
    organelle_name: str = set_organelle_name(seq)
    initialise_organelle_info(data, organelle_name)
    set_additional_organelle_values(seq, organelle, data, organelle_name)
    return organelle


def add_organelle_entries(data: dict, organelles: dict) -> None:
    """
    Adds entries for co-assembled organelles to the provided data dictionary.

    Args:
        data (dict): A dictionary containing processed data.
        organelles (dict): A dictionary containing sequence data for co-assembled
            organelles.

    Returns:
        None
    """
    if not organelles:
        return
    data["organelles"] = []
    for seq in organelles.values():
        try:
            organelle = set_organelle_values(data, seq)
            data["organelles"].append(organelle)
        except Exception as err:
            print("ERROR: ", err)
            raise err


def add_chromosome_entries(data: dict, chromosomes: list[dict]) -> None:
    """
    Adds feature entries for assembled chromosomes to the provided data object.

    Args:
        data (dict): A dictionary containing processed data.
        chromosomes (list): A list of dictionaries containing sequence data for
            assembled chromosomes.

    Returns:
        None
    """
    data["chromosomes"] = []
    for seq in chromosomes:
        data["chromosomes"].append(
            {
                "assembly_id": data["processedAssemblyInfo"]["genbankAccession"],
                "sequence_id": seq["genbank_accession"],
                "start": 1,
                "end": seq["length"],
                "strand": 1,
                "length": seq["length"],
                "midpoint": round(seq["length"] / 2),
                "midpoint_proportion": 0.5,
                "seq_proportion": seq["length"]
                / int(data["assemblyStats"]["totalSequenceLength"]),
            }
        )


def is_chromosome(seq: dict) -> bool:
    """
    Determines if the given sequence data represents an assembled chromosome.

    Args:
        seq (dict): A dictionary containing sequence data.

    Returns:
        bool: True if the sequence data represents an assembled chromosome, False
            otherwise.
    """
    return seq["role"] == "assembled-molecule"


def is_non_nuclear(seq: dict) -> bool:
    """
    Determines if the given sequence data represents a non-nuclear sequence.

    Args:
        seq (dict): A dictionary containing sequence data.

    Returns:
        bool: True if the sequence data represents a non-nuclear sequence, False
            otherwise.
    """
    return seq["assembly_unit"] == "non-nuclear"


def is_assigned_to_chromosome(seq: dict) -> bool:
    """
    Determines if the given sequence data represents a sequence that is assigned to a
    chromosome.

    Args:
        seq (dict): A dictionary containing sequence data.

    Returns:
        bool: True if the sequence data represents a sequence that is assigned to a
            chromosome, False otherwise.
    """
    return (
        seq["assembly_unit"] == "Primary Assembly"
        and seq["assigned_molecule_location_type"]
        in [
            "Chromosome",
            "Linkage Group",
        ]
        and seq["role"] in ["assembled-molecule", "unlocalized-scaffold"]
    )


def check_ebp_criteria(
    data: dict, span: int, chromosomes: list, assigned_span: int
) -> bool:
    """
    Checks if the given assembly data meets the EBP (Earth BioGenome Project) criteria.

    Args:
        data (dict): A dictionary containing assembly statistics and information.
        span (int): The total span of the assembly.
        chromosomes (list): A list of chromosome names.
        assigned_span (int): The total span of the sequences assigned to chromosomes.

    Returns:
        None: This function modifies the `data` dictionary in-place to add the processed
            assembly statistics.
    """
    contig_n50 = int(data["assemblyStats"].get("contigN50", 0))
    scaffold_n50 = int(data["assemblyStats"].get("scaffoldN50", 0))
    assignedProportion = None
    if not chromosomes:
        return False
    data["processedAssemblyStats"] = {}
    assignedProportion = assigned_span / span
    standardCriteria = []
    if contig_n50 >= 1000000 and scaffold_n50 >= 10000000:
        standardCriteria.append("6.7")
    if assignedProportion >= 0.9:
        if contig_n50 >= 1000000:
            standardCriteria.append("6.C")
        elif scaffold_n50 < 1000000 and contig_n50 >= 100000:
            standardCriteria.append("5.C")
        elif scaffold_n50 < 10000000 and contig_n50 >= 100000:
            standardCriteria.append("5.6")
    if standardCriteria:
        data["processedAssemblyStats"]["ebpStandardDate"] = data["assemblyInfo"][
            "releaseDate"
        ]
        data["processedAssemblyStats"]["ebpStandardCriteria"] = standardCriteria
    data["processedAssemblyStats"]["assignedProportion"] = assignedProportion
    return False


def process_sequence_report(data: dict):
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
    organelles: defaultdict[str, list] = defaultdict(list)
    try:
        report = fetch_sequences_report(accession)
        chromosomes: list = []
        assigned_span = 0
        for seq in report:
            if is_non_nuclear(seq):
                organelles[seq["chr_name"]].append(seq)
            elif is_assigned_to_chromosome(seq):
                assigned_span += seq["length"]
                if is_chromosome(seq):
                    chromosomes.append(seq)
    except subprocess.TimeoutExpired:
        print(f"ERROR: Timeout fetching sequence report for {accession}")
        return

    add_organelle_entries(data, organelles)
    check_ebp_criteria(data, span, chromosomes, assigned_span)
    add_chromosome_entries(data, chromosomes)


def update_organelle_info(data: dict, row: dict) -> None:
    """Update organelle info in data dict with fields from row.

    Args:
        data (dict): A dictionary containing the organelle information.
        row (dict): A dictionary containing the fields to update the organelle
        information with.

    Returns:
        None: This function modifies the `data` dictionary in-place.
    """
    for organelle in data.get("organelles", []):
        organelle.update(
            {
                k: row[k]
                for k in row.keys()
                & {
                    "taxId",
                    "organismName",
                    "commonName",
                    "releaseDate",
                    "submitter",
                    "bioProjectAccession",
                    "biosampleAccession",
                }
            }
        )


def process_assembly_report(data: dict, previous_data: Optional[dict]) -> dict:
    """Process assembly level information.

    This function takes a data dictionary and an optional previous_data dictionary, and
    updates the 'processedAssemblyInfo' field in the data dictionary with information
    about the assembly's RefSeq and GenBank accessions. It also checks if the current
    assembly is the primary assembly based on the 'refseqCategory' field in the
    'assemblyInfo' dictionary.

    Args:
        data (dict): A dictionary containing the assembly information.
        previous_data (dict, optional): A dictionary containing previous assembly
        information, used to determine if the current assembly is the same as the
        previous one.

    Returns:
        dict: The updated data dictionary.
    """
    data["processedAssemblyInfo"] = {"organelle": "nucleus"}
    if "pairedAccession" in data:
        if data["pairedAccession"].startswith("GCF_"):
            data["processedAssemblyInfo"]["refseqAccession"] = data["pairedAccession"]
            data["processedAssemblyInfo"]["genbankAccession"] = data["accession"]
        else:
            data["processedAssemblyInfo"]["refseqAccession"] = data["accession"]
            data["processedAssemblyInfo"]["genbankAccession"] = data["pairedAccession"]
    else:
        data["processedAssemblyInfo"]["genbankAccession"] = data["accession"]
    if (
        previous_data
        and data["processedAssemblyInfo"]["genbankAccession"]
        == previous_data["processedAssemblyInfo"]["genbankAccession"]
    ):
        data = {
            **previous_data,
            **data,
        }
    if "refseqCategory" in data.get("assemblyInfo", {}):
        data["processedAssemblyInfo"]["primaryValue"] = 1
    return data


def set_feature_headers() -> list[str]:
    """Set chromosome headers.

    Returns:
        list: The list of headers.
    """
    return [
        "assembly_id",
        "sequence_id",
        "start",
        "end",
        "strand",
        "length",
        "midpoint",
        "midpoint_proportion",
        "seq_proportion",
    ]


def append_features(
    features: list[dict], headers: list[str], features_path: str
) -> None:
    """Append features to a TSV file.

    Args:
        features (list): A list of dictionaries containing features.
        headers (list): A list of column headers.
        features_path (str): The path to the output TSV file.

    Returns:
        None
    """
    gh_utils.append_to_tsv(headers, features, {"file_name": features_path})
    return None


def convert_keys_to_camel_case(data: dict) -> dict:
    """
    Recursively converts all keys in a dictionary to camel case.

    Args:
        data (dict): The dictionary to convert.

    Returns:
        dict: The dictionary with keys converted to camel case.
    """
    converted_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            value = convert_keys_to_camel_case(value)
        converted_key = "".join(
            word.capitalize() if i > 0 else word
            for i, word in enumerate(key.split("_"))
        )
        converted_data[converted_key] = value
    return converted_data


def main():
    """
    Parses a JSONL file containing NCBI dataset information, processes the data,
    and writes the results to a TSV file.

    Args:
        args (argparse.Namespace): The command-line arguments, including the path
            to the JSONL file and the configuration file.
        config (dict): The configuration settings loaded from the YAML file.
        meta (dict): Metadata about the dataset, including the output file name.
        headers (list[str]): The expected headers for the output TSV file.
        parse_fns (dict[str, callable]): Functions for parsing specific fields in
            the JSONL data.
        previous_parsed (dict[str, dict]): The previously parsed data, keyed by
            GenBank accession number.

    Returns:
        None
    """
    args = parse_args()
    config = gh_utils.load_yaml(args.config)
    meta = gh_utils.get_metadata(config, args.config)
    headers = gh_utils.set_headers(config)
    parse_fns = gh_utils.get_parse_functions(config)
    try:
        previous_parsed = gh_utils.load_previous(
            meta["file_name"], "genbankAccession", headers
        )
    except Exception:
        previous_parsed = {}
    parsed = {}
    previous_data = {}
    feature_headers = set_feature_headers()
    feature_file = args.features
    if feature_file is not None:
        try:
            previous_features = gh_utils.load_previous(
                args.features, "assembly_id", feature_headers
            )
        except Exception:
            previous_features = {}
        if feature_file.endswith(".gz"):
            feature_file = feature_file[:-3]
        gh_utils.write_tsv({}, feature_headers, {"file_name": feature_file})

    ctr = 0
    for data in gh_utils.parse_jsonl_file(args.file):
        if "accession" not in data:
            data = convert_keys_to_camel_case(data=data["reports"][0])
        data = process_assembly_report(data, previous_data)
        accession = data["processedAssemblyInfo"]["genbankAccession"]
        print(accession, file=sys.stderr)
        if accession in previous_parsed:
            previous_row = previous_parsed[accession]
            if data["assemblyInfo"]["releaseDate"] == previous_row["releaseDate"]:
                row = previous_row
                if (
                    args.features is not None
                    and accession in previous_features
                    and accession not in parsed
                ):
                    append_features(
                        previous_features[accession], feature_headers, feature_file
                    )
                parsed[accession] = row
                continue
        if (
            args.features is not None
            and accession not in parsed
            and data["assemblyInfo"]["assemblyLevel"]
            in ["Chromosome", "Complete Genome"]
        ):
            process_sequence_report(data)
            ctr += 1
        row = gh_utils.parse_report_values(parse_fns, data)
        if accession not in parsed:
            update_organelle_info(data, row)
        parsed[accession] = row
        previous_data = data
        if args.features is not None and "chromosomes" in data:
            append_features(data["chromosomes"], feature_headers, feature_file)
        if ctr > 10:
            break
    if meta["file_name"].endswith(".gz"):
        meta["file_name"] = meta["file_name"][:-3]
        gh_utils.write_tsv(parsed, headers, meta)
        os.system(f"gzip -f {meta['file_name']}")
    else:
        gh_utils.write_tsv(parsed, headers, meta)

    if feature_file is not None and args.features.endswith(".gz"):
        os.system(f"gzip -f {feature_file}")


if __name__ == "__main__":
    main()
