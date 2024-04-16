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

from dotenv import load_dotenv
from genomehubs import utils as gh_utils
from tolkein import tolog

LOGGER = tolog.logger(__name__)


def parse_arguments():
    """Parse command line arguments."""
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


def split_chunks(values, split_val):
    """Split a list of values into chunks at a certain value."""
    index = 0

    def chunk_index(val):
        nonlocal index
        if val == split_val:
            index += 1
        return index

    return groupby(values, chunk_index)


def read_exp_xml(node, obj):
    """Read values from ExpXml section."""
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


def read_runs(node, obj):
    """Read values from Runs section."""
    if "runs" not in obj:
        obj["runs"] = []
    for child in node:
        obj["runs"].append(
            {"accession": child.get("acc"), "reads": child.get("total_spots")}
        )


def open_file_based_on_extension(file_path, *_, **kwargs):
    if file_path.endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf8", **kwargs)
    else:
        return open(file_path, "r", encoding="utf8", **kwargs)


def parse_sra_xml(xml_file):
    """Parse an SRA xml file."""
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


def group_by_taxon(rows, grouped=None):
    """
    Group SRA runs by taxon.

    Keep the most recent 10 rows only.
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


def load_sra_tsv(file):
    """Load rows from a TSV file."""
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


def sra_parser(previous_parsed, args):
    """Parse SRA efetch xml."""
    xml_file = args.file
    # Load newer runs from xml
    rows = parse_sra_xml(xml_file)
    return group_by_taxon(rows, grouped=previous_parsed)


def fetch_sra_data(config, args):
    """Fetch the latest SRA data."""
    source_date = (
        config.get("file", {}).get("source_date", "2024-01-01").replace("-", "/")
    )
    cmd = (
        f"esearch -db sra -query '(txid{args.root_taxon}[organism:exp])' "
        f"-api_key {args.api_key} -mindate {source_date} "
        f"-maxdate {get_yesterday()} | efetch -db sra -format docsum "
        f"-api_key {args.api_key} > {args.file}"
    )
    print(cmd)
    return
    subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        timeout=30,
    )


def get_day_before(date_str):
    if "-" in date_str:
        return (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime(
            "%Y/%m/%d"
        )
    return (datetime.strptime(date_str, "%Y/%m/%d") - timedelta(days=1)).strftime(
        "%Y/%m/%d"
    )


def get_yesterday():
    return (date.today() - timedelta(days=1)).strftime("%Y/%m/%d")


def main():
    args = parse_arguments()
    config = gh_utils.load_yaml(args.config)
    meta = gh_utils.get_metadata(config, args.config)
    headers = gh_utils.set_headers(config)
    # file = args.file
    # config = args.config
    # root_taxon = args.root_taxon
    if args.latest:
        LOGGER.info("Fetching latest SRA data")
        sra_data = fetch_sra_data(config, args)
    # Load older runs from tsv
    previous_parsed = load_sra_tsv(meta["file_name"])
    sra_data = sra_parser(previous_parsed, args)
    gh_utils.print_to_tsv(headers, sra_data, meta)


if __name__ == "__main__":
    main()
