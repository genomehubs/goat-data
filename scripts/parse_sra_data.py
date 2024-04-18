#!/usr/bin/env python3

import argparse
import csv
import gzip
import os
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Any

from dotenv import load_dotenv
from genomehubs import utils as gh_utils
from tolkein import tolog

LOGGER = tolog.logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    This function parses the command line arguments provided by the user.
    It uses the argparse module to define and parse the arguments.

    Returns:
        argparse.Namespace: An object containing the parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="Parse SRA data.")
    parser.add_argument("-f", "--file", help="Path to the SRA data file")
    parser.add_argument(
        "-c", "--config", required=True, help="Path to the configuration file"
    )
    parser.add_argument("-r", "--root-taxon", default="2759", help="Root taxon ID")
    parser.add_argument(
        "-l", "--latest", action="store_true", help="Fetch the latest SRA data"
    )
    parser.add_argument("-k", "--api-key", help="API key for NCBI")
    args = parser.parse_args()
    for file in (args.file, args.config):
        if file is not None and not os.path.isfile(file):
            LOGGER.error(f"File not found: {file}")
            sys.exit(1)
    if args.latest and not args.api_key:
        load_dotenv()
        args.api_key = os.getenv("NCBI_API_KEY")
        if not args.api_key:
            LOGGER.error("API key required for fetching latest SRA data")
            sys.exit(1)
    return args


def split_chunks(values: list[Any], split_val: Any) -> Any:
    """
    Split a list of values into chunks at a certain value.

    Args:
        values (List[Any]): The list of values to be split into chunks.
        split_val (Any): The value at which to split the list.

    Returns:
        Any: An iterator of chunks, where each chunk is a sublist of values.

    Example:
        >>> values = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        >>> split_val = 5
        >>> chunks = split_chunks(values, split_val)
        >>> for chunk in chunks:
        ...     print(chunk)
        [1, 2, 3, 4]
        [6, 7, 8, 9]
    """
    index = 0

    def chunk_index(val):
        nonlocal index
        if val == split_val:
            index += 1
        return index

    return groupby(values, chunk_index)


def read_exp_xml(node: ET.Element, obj: dict[str, Any]) -> None:
    """
    Read values from ExpXml section.

    Args:
        node (xml.etree.ElementTree.Element): The XML node containing the ExpXml section.
        obj (dict): The dictionary to store the parsed values.

    Returns:
        None
    """
    for child in node:
        tag = child.tag
        if tag == "Bioproject":
            obj["bioproject"] = child.text
        elif tag == "Biosample":
            obj["biosample"] = child.text
        elif tag == "Organism":
            obj["taxon_id"] = child.get("taxid")
        elif tag == "Experiment":
            obj["sra_accession"] = child.get("acc")
        elif tag == "Summary":
            obj["platform"] = child.findtext("Platform")
        elif tag == "Library_descriptor":
            obj["library_source"] = child.findtext("LIBRARY_SOURCE").lower()


def read_runs(node: ET.Element, obj: dict[str, Any]) -> None:
    """
    Read values from Runs section.

    Parameters:
    - node: XML element representing the Runs section.
    - obj: Dictionary to store the parsed values.

    Returns:
    None

    This function parses the Runs section of an XML element and extracts the accession and total_spots
    values for each child element. It then appends the parsed values to the 'runs' list in the 'obj' dictionary.
    """
    if "runs" not in obj:
        obj["runs"] = []
    for child in node:
        obj["runs"].append(
            {"accession": child.get("acc"), "reads": child.get("total_spots")}
        )


def open_file_based_on_extension(file_path, *_, **kwargs):
    """
    Opens a file based on its extension.

    Args:
        file_path (str): The path to the file.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        file object: The opened file object.

    Raises:
        None

    """
    if file_path.endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf8", **kwargs)
    else:
        return open(file_path, "r", encoding="utf8", **kwargs)


def parse_sra_xml(xml_file: str) -> list[dict]:
    """
    Parse an SRA xml file.

    Args:
        xml_file (str): The path to the SRA xml file.

    Returns:
        list: A list of dictionaries containing parsed information from the xml file.
    """
    rows = []
    with open_file_based_on_extension(xml_file) as container_file:
        for doc_num, doc in split_chunks(
            container_file, '<?xml version="1.0" encoding="UTF-8" ?>\n'
        ):
            LOGGER.info(f"processing sub-document #{doc_num}")
            LOGGER.info(len(rows))
            lines = list(doc)
            try:
                root = ET.fromstringlist(lines)
            except Exception:
                continue
            for doc_summary in root.iter("DocumentSummary"):
                obj = {}
                for child in doc_summary:
                    tag = child.tag
                    if tag == "CreateDate":
                        obj["date"] = child.text
                    elif tag == "ExpXml":
                        read_exp_xml(child, obj)
                    elif tag == "Runs":
                        read_runs(child, obj)
                    continue
                rows.append(obj)
    return rows


def group_by_taxon(rows: list, grouped=None) -> list[dict]:
    """
    Group SRA runs by taxon.

    Keep the most recent 10 rows only.

    Parameters:
    - rows (list): A list of dictionaries representing SRA runs.
    - grouped (dict, optional): A dictionary to store the grouped data. If not provided, a new dictionary will be created.

    Returns:
    - rows (list): A list of dictionaries representing the grouped SRA runs.

    Example:
    ```
    rows = [
        {
            "taxon_id": 123,
            "runs": [
                {
                    "accession": "SRR123",
                    "reads": 100
                },
                {
                    "accession": "SRR456",
                    "reads": 200
                }
            ]
        },
        {
            "taxon_id": 456,
            "runs": [
                {
                    "accession": "SRR789",
                    "reads": 150
                }
            ]
        }
    ]

    grouped = group_by_taxon(rows)
    print(grouped)
    ```
    Output:
    ```
    [
        {
            "taxon_id": 123,
            "sra_accession": "SRR123;SRR456",
            "run_accession": "SRR123;SRR456",
            "library_source": "",
            "platform": "",
            "reads": "100;200",
            "total_reads": 300,
            "total_runs": 2
        },
        {
            "taxon_id": 456,
            "sra_accession": "SRR789",
            "run_accession": "SRR789",
            "library_source": "",
            "platform": "",
            "reads": "150",
            "total_reads": 150,
            "total_runs": 1
        }
    ]
    ```
    """
    if grouped is None or not grouped:
        grouped = defaultdict(lambda: {"count": 0, "reads": 0, "runs": []})
    for obj in sorted(rows, key=itemgetter("date")):
        try:
            taxon_id = obj["taxon_id"]
        except Exception:
            continue
        for run in obj["runs"]:
            try:
                row = {
                    **obj,
                    "run_accession": run["accession"],
                    "reads": int(run["reads"]),
                }
            except Exception:
                continue
            row.pop("runs")
            grouped[taxon_id]["runs"].insert(0, row)
            grouped[taxon_id]["count"] += 1
            grouped[taxon_id]["reads"] += row["reads"]
            if len(grouped[taxon_id]["runs"]) > 10:
                grouped[taxon_id]["runs"].pop()
    rows = [
        {
            "taxon_id": taxon_id,
            "sra_accession": ";".join([item["sra_accession"] for item in obj["runs"]]),
            "run_accession": ";".join([item["run_accession"] for item in obj["runs"]]),
            "library_source": ";".join(
                [item["library_source"] for item in obj["runs"]]
            ),
            "platform": ";".join([item["platform"] for item in obj["runs"]]),
            "reads": ";".join([str(item["reads"]) for item in obj["runs"]]),
            "total_reads": obj["reads"],
            "total_runs": obj["count"],
        }
        for taxon_id, obj in grouped.items()
    ]
    return rows


def load_sra_tsv(file: str) -> dict:
    """
    Load rows from a TSV file and group them based on taxon_id.

    Args:
        file (str): The path to the TSV file.

    Returns:
        dict: A dictionary containing the grouped data. The keys are taxon_ids and the values are dictionaries
              with the following keys:
              - count: The total number of runs for the taxon_id.
              - reads: The total number of reads for the taxon_id.
              - runs: A list of dictionaries, each representing a run. Each run dictionary has the following keys:
                - run_accession: The accession number of the run.
                - sra_accession: The accession number of the SRA.
                - library_source: The source of the library.
                - platform: The platform used for the run.
                - reads: The number of reads for the run.
    """
    if not os.path.isfile(file):
        return None
    grouped = defaultdict(lambda: {"count": 0, "reads": 0, "runs": []})
    with open_file_based_on_extension(file, newline="") as tsv_file:
        reader = csv.DictReader(tsv_file, delimiter="\t")
        for row in reader:
            taxon_id = row["taxon_id"]
            total_runs = row["total_runs"]
            total_reads = row["total_reads"]
            grouped[taxon_id]["count"] = int(total_runs)
            grouped[taxon_id]["reads"] = int(total_reads)
            for key in (
                "run_accession",
                "sra_accession",
                "library_source",
                "platform",
                "reads",
            ):
                row[key] = row[key].split(";")
            for index, run_accession in enumerate(row["run_accession"]):
                grouped[taxon_id]["runs"].append(
                    {
                        "run_accession": run_accession,
                        "sra_accession": row["sra_accession"][index],
                        "library_source": row["library_source"][index],
                        "platform": row["platform"][index],
                        "reads": int(row["reads"][index]),
                    }
                )
    return grouped


def sra_parser(previous_parsed: list, args: argparse.Namespace) -> list:
    """Parse SRA efetch xml.

    This function takes in the previously parsed data and the command line arguments.
    It parses the SRA efetch xml file specified in the arguments and returns the parsed data
    grouped by taxon.

    Args:
        previous_parsed (list): The previously parsed data.
        args (Namespace): The command line arguments.

    Returns:
        list: The parsed data grouped by taxon.
    """
    xml_file = args.file
    rows = parse_sra_xml(xml_file)
    return group_by_taxon(rows, grouped=previous_parsed)


def fetch_sra_data(config: dict, args: argparse.Namespace) -> None:
    """
    Fetches the latest SRA data.

    Args:
        config (dict): A dictionary containing configuration settings.
        args (Namespace): An object containing command-line arguments.

    Returns:
        None
    """
    source_date = (
        config.get("file", {}).get("source_date", "2024-01-01").replace("-", "/")
    )
    cmd = (
        f"esearch -db sra -query '(txid{args.root_taxon}[organism:exp])' "
        f"-api_key {args.api_key} -mindate {source_date} "
        f"-maxdate {get_yesterday()} | efetch -db sra -format docsum "
        f"-api_key {args.api_key} > {args.file}"
    )
    subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        timeout=30,
    )


def get_yesterday() -> str:
    """
    Returns the date of yesterday in the format 'YYYY/MM/DD'.

    Returns:
        str: The date of yesterday in the format 'YYYY/MM/DD'.
    """
    return (date.today() - timedelta(days=1)).strftime("%Y/%m/%d")


def main() -> None:
    """
    Main function for parsing SRA data.

    This function parses SRA data based on the provided configuration and command line arguments.
    It loads the configuration file, retrieves metadata, sets headers, fetches latest SRA data if specified,
    loads previously parsed data, parses SRA data, and prints the parsed data to a TSV file.

    Args:
        None

    Returns:
        None
    """
    args = parse_arguments()
    config = gh_utils.load_yaml(args.config)
    meta = gh_utils.get_metadata(config, args.config)
    headers = gh_utils.set_headers(config)
    if args.latest:
        LOGGER.info("Fetching latest SRA data")
        sra_data = fetch_sra_data(config, args)
    previous_parsed = load_sra_tsv(meta["file_name"])
    sra_data = sra_parser(previous_parsed, args)
    gh_utils.print_to_tsv(headers, sra_data, meta)


if __name__ == "__main__":
    main()
