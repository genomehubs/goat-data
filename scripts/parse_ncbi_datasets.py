#!/usr/bin/env python

import argparse
import contextlib
import csv
import gzip
import json
import math
import pathlib
import subprocess
from collections import defaultdict
from collections.abc import Callable, Generator, Iterator
from functools import reduce
from typing import IO, Any, Optional, Union

import yaml


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
    return parser.parse_args()


def parse_jsonl_file(file_path: str) -> Generator[dict, None, None]:
    """
    Parses a JSONL file and yields each line as a JSON object.

    Args:
        file_path (str): The path to the JSONL file to parse.

    Yields:
        dict: A JSON object parsed from each line in the JSONL file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    if not pathlib.Path(file_path).exists():
        raise FileNotFoundError(f"{file_path} does not exist")

    with open(file_path, "r") as f:
        for line in f:
            yield json.loads(line)


def load_yaml_config(config_path: str) -> dict:
    """
    Loads a YAML configuration file from the specified path.

    Args:
        config_path (str): The path to the YAML configuration file.

    Returns:
        dict: The configuration data loaded from the YAML file.

    Raises:
        FileNotFoundError: If the specified configuration file does not exist.
    """
    if not pathlib.Path(config_path).exists():
        raise FileNotFoundError(f"{config_path} does not exist")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def parse_path(path_str: str) -> Optional[Any]:
    """
    Parses a dot-separated path string and retrieves the corresponding data from a
    nested dictionary or list of dictionaries.

    Args:
        path_str (str): A dot-separated path string to the desired data.

    Returns:
        The data at the specified path, or None if the path does not exist.
    """
    keys = path_str.split(".")

    def get_key(data: dict[str, Any] | list[dict[str, Any]], key: str) -> Optional[Any]:
        """
        Retrieves the value of a key from a dictionary or a list of dictionaries.

        Args:
            data (dict or list): The dictionary or list of dictionaries to search.
                key (str): The key to search for.

        Returns:
            The value of the key, or None if the key does not exist or the data is not
            a dictionary or list of dictionaries.
        """
        if isinstance(data, dict):
            return data.get(key)
        elif isinstance(data, list):
            if "==" in key:
                key, value = key.split("==")
                return [d for d in data if d.get(key) == value]
            flat_list = []
            for d in data:
                if key not in d:
                    continue
                if isinstance(d[key], list):
                    flat_list.extend(d[key])
                else:
                    flat_list.append(d[key])
            return flat_list
        else:
            return None

    def get_data(data: dict[str, Any] | list[dict[str, Any]]) -> Optional[Any]:
        """
        Recursively retrieves the value at the specified path from a nested dictionary
        or list of dictionaries.

        Args:
            data (dict or list): The dictionary or list of dictionaries to search.

        Returns:
            The value at the specified path, or None if the path does not exist.
        """
        return reduce(
            lambda d, key: get_key(d, key),
            keys,
            data,
        )

    return get_data


def get_path_header(data: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """
    Yields the path and header for each object in the "attributes", "identifiers", and
    "taxonomy" sections of the provided data.

    Args:
        data (dict): The data to search for path and header information.

    Yields:
        tuple[str, str]: The path and header for each matching object.
    """
    for section in ["attributes", "identifiers", "metadata", "names", "taxonomy"]:
        for _, obj in data.get(section, {}).items():
            if "path" in obj and "header" in obj:
                yield obj["path"], obj["header"]


def set_headers(config: dict[str, Any]) -> list[str]:
    """
    Retrieves a list of all headers defined in the "attributes", "identifiers",
    "metadata", "names", and "taxonomy" sections of the provided configuration.

    Args:
        config (dict): The configuration dictionary containing the section data.

    Returns:
        list: A list of all unique headers found in the specified sections.
    """
    headers: list[str] = []
    for section in ["attributes", "identifiers", "metadata", "names", "taxonomy"]:
        for value in config.get(section, {}).values():
            if "header" in value and value["header"] not in headers:
                headers.append(value["header"])
    return headers


def get_parse_functions(
    config: dict[str, Any]
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """
    Generates a dictionary of parse functions based on the path and header information
    extracted from the "attributes", "identifiers", and "taxonomy" sections of the
    provided configuration data.

    The `get_path_header` function is used to iterate through the relevant sections of
    the configuration data and yield the path and header for each object. The
    `parse_path` function is then used to create a parse function for each path, and
    the resulting dictionary is returned.

    Args:
        config (dict): The configuration data to extract path and header information
            from.

    Returns:
        dict: A dictionary mapping headers to their corresponding parse functions.
    """
    return {header: parse_path(path) for path, header in get_path_header(config)}


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


def set_organelle_name(seq: dict) -> str:
    """
    Determines the organelle type (mitochondrion or plastid) based on the assigned
    molecule location type in the provided sequence data.

    Args:
        seq (dict): A dictionary containing sequence data, including the
            "assigned_molecule_location_type" field.

    Returns:
        str: The organelle type, either "mitochondrion" or "plastid".
    """
    return (
        "mitochondrion"
        if seq[0]["assigned_molecule_location_type"] == "Mitochondrion"
        else "plastid"
    )


def is_assembled_molecule(seq: dict) -> bool:
    """
    Determines if the provided sequence data represents an assembled molecule.

    Args:
        seq (dict): A dictionary containing sequence data, including the "role" field.

    Returns:
        bool: True if the sequence data represents an assembled molecule, False
            otherwise.
    """
    return len(seq) == 1 and seq[0]["role"] == "assembled-molecule"


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


def initialiseOrganelleInfo(data: dict, organelle_name: str):
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
    initialiseOrganelleInfo(data, organelle_name)
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


def add_chromosome_entries(obj: dict, chromosomes: list[dict]) -> None:
    """
    Adds feature entries for assembled chromosomes to the provided data object.

    Args:
        obj (dict): A dictionary containing processed data.
        chromosomes (list): A list of dictionaries containing sequence data for
            assembled chromosomes.

    Returns:
        None
    """
    obj["chromosomes"] = []
    for seq in chromosomes:
        obj["chromosomes"].append(
            {
                "sequence_id": seq["genbank_accession"],
                "start": 1,
                "end": seq["length"],
                "strand": 1,
                "length": seq["length"],
                "midpoint": math.round(seq["length"] / 2),
                "midpoint_proportion": 0.5,
                "seq_proportion": seq["length"] / obj["totalSequenceLength"],
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
        return
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

    add_organelle_entries(data, organelles)
    check_ebp_criteria(data, span, chromosomes, assigned_span)


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


def parse_report_values(
    parse_fns: dict[str, Callable[[dict], Any]], data: dict
) -> dict[str, Any]:
    """
    Applies a set of parsing functions to the provided data and returns a dictionary
    with the parsed values.

    Args:
        parse_fns (dict): A dictionary mapping header names to parsing functions.
        data (dict): The data to be parsed.

    Returns:
        dict: A dictionary with the parsed values, where the keys are the header names
            and the values are the results of applying the corresponding parsing
            functions to the data.
    """
    return {header: parse_fn(data) for header, parse_fn in parse_fns.items()}


def format_entry(entry: Union[str, list], key: str, meta: dict) -> str:
    """
    Formats a single entry in a dictionary, handling the case where the entry is a list.

    Args:
        entry (Union[str, list]): The entry to be formatted, which may be a single
            value or a list of values.
        key (str): The key associated with the entry.
        meta (dict): A dictionary containing metadata, including a "separators"
            dictionary that maps keys to separator strings.

    Returns:
        str: The formatted entry, where list elements are joined using the separator
            specified in the "separators" dictionary.
    """
    if not isinstance(entry, list):
        return str(entry)
    return (
        meta["separators"].get(key, ",").join([str(e) for e in entry if e is not None])
    )


def print_to_tsv(headers: list[str], rows: list[dict], meta: dict):
    """
    Writes the provided headers and rows to a TSV file with the specified file name.

    Args:
        headers (list[str]): A list of column headers to write to the file.
        rows (list[dict]): A list of dictionaries, where each dictionary represents a
            row of data and the keys correspond to the column headers.
        meta (dict): A dictionary containing metadata, including the "file_name" key
            which specifies the output file name.
    """
    with open(meta["file_name"], "w") as f:
        f.write("\t".join(headers) + "\n")
        for row in rows:
            f.write(
                "\t".join(
                    [format_entry(row.get(col, []), col, meta) for col in headers]
                )
                + "\n"
            )


def get_metadata(config: dict, yaml_file: str) -> dict:
    """
    Retrieves metadata information from a configuration file, including the output file
    name and separator values for specific keys.

    Args:
        config (dict): A dictionary containing the configuration settings.
        yaml_file (str): The path to the YAML configuration file.

    Returns:
        dict: A dictionary containing the output file name and a dictionary of
            separators for specific keys.
    """
    yaml_dir = pathlib.Path(yaml_file).parent
    file_name = config.get("file", {}).get("name", "output.tsv")
    separators: dict[str, str] = {}
    with contextlib.suppress(KeyError):
        for key, value in config["attributes"].items():
            separators[key] = value.get("separator", ",")
    return {
        "file_name": f"{yaml_dir}/{file_name}",
        "separators": separators,
    }


def write_tsv(parsed: dict[str, dict], headers: list[str], meta: dict):
    """
    Writes the parsed data to a TSV file using the provided headers and metadata.

    Args:
        parsed (dict[str, dict]): A dictionary containing the parsed data, where the
            keys are the row identifiers and the values are dictionaries representing
            the rows.
        headers (list[str]): A list of column headers to write to the file.
        meta (dict): A dictionary containing metadata, including the "file_name" key
            which specifies the output file name.
    """
    rows = list(parsed.values())
    print_to_tsv(headers, rows, meta)


def parse_previous(f: IO[str], headers: list[str]) -> dict[str, dict[str, str]]:
    """Parses a TSV file containing NCBI dataset information and returns a
    dictionary of rows, where the keys are the GenBank accession numbers and
    the values are dictionaries representing the rows.

    Args:
        f (IO[str]): The file-like object containing the TSV data.
        headers (list[str]): A list of column headers expected in the TSV file.

    Returns:
        dict[str, dict[str, str]]: A dictionary where the keys are the GenBank
            accession numbers and the values are dictionaries representing the
            rows.

    Raises:
        ValueError: If the headers in the TSV file do not match the provided
            headers.
    """
    reader = csv.reader(f, delimiter="\t")
    header = next(reader)
    if header != headers:
        raise ValueError("Headers do not match")

    rows: dict[str, dict[str, str]] = {}
    for row in reader:
        row_dict = {header[i]: row[i] for i in range(len(header))}
        rows[row_dict["genbankAccession"]] = row_dict
    return rows


def load_previous(file_path: str, headers: list[str]) -> dict[str, dict]:
    """
    Loads the previous data from a TSV file at the given file path.

    Args:
        file_path (str): The path to the TSV file containing the previous data.
        headers (list[str]): The expected headers for the TSV file.

    Returns:
        dict[str, dict]: A dictionary where the keys are the "genbankAccession" values
            and the values are dictionaries representing the rows.
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        return {}

    open_fn = gzip.open if file_path.suffix == ".gz" else open
    with open_fn(file_path, "rt") as f:
        return parse_previous(f, headers)


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
    config = load_yaml_config(args.config)
    meta = get_metadata(config, args.config)
    headers = set_headers(config)
    parse_fns = get_parse_functions(config)
    previous_parsed = load_previous(meta["file_name"], headers)
    parsed = {}
    previous_data = {}
    ctr = 0

    for data in parse_jsonl_file(args.file):
        ctr += 1
        data = process_assembly_report(data, previous_data)
        accession = data["processedAssemblyInfo"]["genbankAccession"]
        if accession in previous_parsed:
            previous_row = previous_parsed[accession]
            if data["assemblyInfo"]["releaseDate"] == previous_row["releaseDate"]:
                row = previous_row
                parsed[accession] = row
                continue
        if accession not in parsed:
            process_sequence_report(data)
        row = parse_report_values(parse_fns, data)
        if accession not in parsed:
            update_organelle_info(data, row)
        parsed[accession] = row
        previous_data = data
        if ctr >= 115:
            break
    write_tsv(parsed, headers, meta)


if __name__ == "__main__":
    main()
