#!/usr/bin/env python3
"""
Parse RefSeq collection records for organelle sequences.
"""


import argparse
import contextlib
import gzip
import os
import re
from collections import Counter
from typing import Optional
from urllib.error import ContentTooShortError

from Bio import SeqIO, SeqRecord
from genomehubs import utils as gh_utils
from tolkein import tofetch, tolog
from tqdm import tqdm

LOGGER = tolog.logger(__name__)

REFSEQ_FTP = "https://ftp.ncbi.nlm.nih.gov/refseq/release"


def refseq_listing(collection: str, min_date: str, retries: int = 5) -> list:
    """Fetch a directory listing for a RefSeq collection.

    Args:
        collection (str): The RefSeq collection to fetch the listing for.
        min_date (str, optional): The minimum date to include in the listing, in the
            format "YYYY-MM-DD". If None, all files will be included.
        retries (int, optional): The number of times to retry the fetch if it fails.
            Defaults to 5.

    Returns:
        list: A list of URLs for the files in the RefSeq collection that match the
            minimum date.
    """
    pattern = re.compile(r"(\w+\.\d+\.genomic\.gbff\.gz).+(\d{4}-\d{2}-\d{2})")
    url = f"{REFSEQ_FTP}/{collection}"
    for _ in range(retries):
        with contextlib.suppress(ContentTooShortError):
            html = tofetch.fetch_url(url)
            break
    listing = []
    for line in html.split("\n"):
        if match := pattern.search(line):
            if min_date is None or match[2] > min_date:
                listing.append(f"{url}/{match[1]}")
    return listing


def parse_references(entry: SeqRecord.SeqRecord, fields: dict = None) -> dict:
    """Parse references from a BioPython SeqRecord entry.

    Args:
        entry (Bio.SeqRecord.SeqRecord): The SeqRecord entry to parse references from.
        fields (dict, optional): A dictionary to store the parsed reference fields in.
            If not provided, a new dictionary will be created.

    Returns:
        dict: A dictionary containing the parsed reference fields, including:
            - sourceYear: The year the reference was published or submitted.
            - sourceTitle: The title of the reference.
            - pubmedId: The PubMed ID of the reference.
            - sourceAuthor: The author(s) of the reference.
    """
    if fields is None:
        fields: dict = {}
    submitted_year: re.Pattern = re.compile(r"Submitted\s\(\d{2}-\w{3}-(\d{4})\)")
    published_year: re.Pattern = re.compile(r"\s\((\d{4})\)[^\(]*$")
    for reference in entry.annotations["references"]:
        if reference.journal == "Unpublished":
            continue
        elif reference.journal.startswith("Submitted"):
            if "sourceAuthor" in fields:
                continue
            fields["sourceYear"] = submitted_year.search(reference.journal)[1]
        elif "sourceAuthor" in fields:
            continue
        else:
            fields["sourceYear"] = published_year.search(reference.journal)[1]
            if reference.title:
                fields["sourceTitle"] = reference.title
            if reference.pubmed_id:
                fields["pubmedId"] = reference.pubmed_id
        if reference.authors:
            fields["sourceAuthor"] = reference.authors
        elif reference.consrtm:
            fields["sourceAuthor"] = reference.consrtm
    return fields


def parse_xrefs(entry: SeqRecord.SeqRecord, fields: dict = None) -> dict:
    """Parse cross-references (xrefs) from a BioPython SeqRecord entry.

    Args:
        entry (Bio.SeqRecord.SeqRecord): The SeqRecord entry to parse xrefs from.
        fields (dict, optional): A dictionary to store the parsed xref fields in.
            If not provided, a new dictionary will be created.

    Returns:
        dict: A dictionary containing the parsed xref fields, including:
            - bioproject: A list of BioProject IDs associated with the entry.
            - biosample: A list of BioSample IDs associated with the entry.
    """
    if fields is None:
        fields: dict = {}
    if entry.dbxrefs:
        bioprojects: list[str] = []
        biosamples: list[str] = []
        for dbxref in entry.dbxrefs:
            with contextlib.suppress(ValueError):
                key, value = dbxref.split(":")
                if key == "BioProject":
                    bioprojects.append(value)
                elif key == "BioSample":
                    biosamples.append(value)
        if bioprojects:
            fields["bioproject"] = bioprojects
        if biosamples:
            fields["biosample"] = biosamples
    return fields


def parse_features(
    entry: SeqRecord.SeqRecord, fields: dict[str, str] = None
) -> dict[str, str]:
    """Parse feature information from a BioPython SeqRecord entry.

    Args:
        entry (Bio.SeqRecord.SeqRecord): The SeqRecord entry to parse features from.
        fields (dict, optional): A dictionary to store the parsed feature fields in.
            If not provided, a new dictionary will be created.

    Returns:
        dict: A dictionary containing the parsed feature fields, including:
            - taxonId: The NCBI Taxonomy ID associated with the entry.
            - sampleLocation: The latitude and longitude of the sample location.
    """
    if fields is None:
        fields = {}
    qualifiers = entry.features[0].qualifiers
    if "db_xref" in qualifiers:
        for xref in qualifiers["db_xref"]:
            key, value = xref.split(":")
            if key == "taxon":
                fields["taxonId"] = value
    if "lat_lon" in qualifiers:
        fields["sampleLocation"] = qualifiers["lat_lon"]
    return fields


def reformat_date(string: str) -> str:
    """
    Reformats a date string in the format "DD-MMM-YYYY" to "YYYY-MM-DD".

    Args:
        string (str): The date string to reformat.

    Returns:
        str: The reformatted date string.
    """
    months = {
        "JAN": "01",
        "FEB": "02",
        "MAR": "03",
        "APR": "04",
        "MAY": "05",
        "JUN": "06",
        "JUL": "07",
        "AUG": "08",
        "SEP": "09",
        "OCT": "10",
        "NOV": "11",
        "DEC": "12",
    }
    parts = re.split(r"[\:\-]", string)
    return f"{parts[2]}-{months[parts[1]]}-{parts[0].zfill(2)}"


def parse_sequence(entry: SeqRecord.SeqRecord, fields: dict) -> bool:
    """
    Parses the sequence information from the provided SeqRecord entry and
    updates the given fields dictionary.

    Args:
        entry (Bio.SeqRecord.SeqRecord): The SeqRecord entry to parse sequence
            information from.
        fields (dict): A dictionary to store the parsed sequence information
            in. This dictionary will be updated in-place.

    Returns:
        bool: True if the sequence was successfully parsed, False if the
            sequence is entirely 'N' characters.
    """
    seqstr = str(entry.seq.upper())
    counter = Counter(seqstr)
    length = len(seqstr)
    fields["nPercent"] = float("%.2f" % (counter["N"] / length * 100))
    if fields["nPercent"] == 100:
        return False
    gc_count = counter["G"] + counter["C"]
    fields["gcPercent"] = float(
        "%.2f" % (gc_count / (gc_count + counter["A"] + counter["T"]) * 100)
    )
    fields["assemblySpan"] = length
    return True


def parse_flatfile(
    flatfile: str, organelle: str, args: argparse.Namespace
) -> list[dict]:
    """Parse a GenBank flatfile.

    Args:
        flatfile (str): The path to the GenBank flatfile to parse.
        organelle (str): The type of organelle to parse from the flatfile.
        args (argparse.Namespace): Command-line arguments passed to the script.

    Returns:
        list[dict]: A list of dictionaries containing the parsed data from the flatfile.
    """
    data: list[dict] = []
    comment_re = re.compile(
        r"(?:derived|identical)\s(?:from|to)\s([\w\d]+).*COMPLETENESS: full length",
        re.DOTALL,
    )
    with gzip.open(flatfile, "rt") as fh:
        gb = SeqIO.parse(fh, "gb")
        for entry in tqdm(gb, mininterval=args.log_interval):
            if (
                args.root_taxon is not None
                and args.root_taxon not in entry.annotations["taxonomy"]
            ):
                continue
            fields: dict = {
                "id": entry.id,
                "organelle": organelle,
                "annotations": entry.annotations,
            }
            if comment := entry.annotations.get("comment", ""):
                if match := comment_re.search(comment):
                    fields["genbankAccession"] = match[1]
                else:
                    continue
            parse_features(entry, fields)
            parse_references(entry, fields)
            fields["releaseDate"] = reformat_date(entry.annotations["date"])
            parse_xrefs(entry, fields)
            try:
                if not parse_sequence(entry, fields):
                    continue
            except Exception:
                LOGGER.warning("Unable to read sequence for %s", entry.id)
                continue
            fields[organelle] = fields
            data.append(fields)
    return data


def parse_listing(
    listing: list[str], organelle: str, args: argparse.Namespace
) -> list[dict]:
    """Parse all URLs in a directory listing.

    Args:
        listing (list[str]): A list of URLs to fetch and parse.
        organelle (str): The type of organelle to parse from the flatfiles.
        args (argparse.Namespace): Command-line arguments passed to the script.

    Returns:
        list[dict]: A list of dictionaries containing the parsed data from the
        flatfiles.
    """
    parsed: list[dict] = []
    for url in listing:
        LOGGER.info("Fetching %s", url)
        flatfile = tofetch.fetch_tmp_file(url)
        LOGGER.info("Parsing %s", url)
        parsed += parse_flatfile(flatfile, organelle, args)
    return parsed


def refseq_organelle_parser(args: argparse.Namespace, min_date: str) -> list[dict]:
    """Fetch and parse RefSeq organelle collections.

    This function fetches and parses RefSeq organelle collections based on the provided
        command-line arguments. It supports parsing multiple organelle types specified
        in the `organelle` argument.

    Args:
        args (argparse.Namespace): Command-line arguments passed to the script.
        min_date (str): The minimum date for the RefSeq organelle collections to be
        parsed.

    Returns:
        list[dict]: A list of dictionaries containing the parsed data from the
        flatfiles.
    """
    organelles = args.organelle
    if not isinstance(organelles, (list, tuple)):
        organelles = [organelles]
    parsed: list[dict] = []
    for organelle in organelles:
        listing = refseq_listing(organelle, min_date)
        parsed += parse_listing(listing, organelle, args)
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the RefSeq organelle data processing script.

    Args:
        -o, --organelle (List[str]): One or both of "mitochondrion" and "plastid".
            Required.
        -c, --config (str): Path to the YAML configuration file. Required.
        -i, --log-interval (int): Interval for logging progress. Default is 1.
        -r, --root-taxon (Optional[str]): Root taxon to filter by. Optional.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Process organelle data.")
    parser.add_argument(
        "-o",
        "--organelle",
        nargs="*",
        choices=["mitochondrion", "plastid"],
        required=True,
        help='One or both of "mitochondrion" and "plastid".',
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "-i",
        "--log-interval",
        type=int,
        default=1,
        required=False,
        help="Interval for logging progress.",
    )
    parser.add_argument(
        "-r",
        "--root-taxon",
        type=Optional[str],
        default=None,
        required=False,
        help="Root taxon to filter by.",
    )

    return parser.parse_args()


def main() -> None:
    """
    Processes RefSeq organelle data using the provided command-line arguments and
    configuration.

    Args:
        args (argparse.Namespace): The parsed command-line arguments.
        config (dict): The loaded YAML configuration.
        meta (dict): The metadata for the data processing.
        headers (list): The headers for the output data.
        parse_fns (dict): The parsing functions for the data.
        previous_parsed (dict): The previously parsed data.
        previous_date (str): The date of the previously parsed data.
        raw_parsed (list): The raw parsed data.
        parsed (list): The parsed data with values transformed.

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
            meta["file_name"], "refseqAccession", headers
        )
    except Exception:
        previous_parsed = {}
    previous_date = config["file"]["source_date"] if previous_parsed else None
    parsed = refseq_organelle_parser(args, previous_date)
    if not parsed:
        return None
    rows = [gh_utils.parse_report_values(parse_fns, data) for data in parsed]

    if meta["file_name"].endswith(".gz"):
        meta["file_name"] = meta["file_name"][:-3]
        gh_utils.print_to_tsv(headers, rows, meta)
        os.system(f"gzip -f {meta['file_name']}")
    else:
        gh_utils.print_to_tsv(headers, rows, meta)


if __name__ == "__main__":
    main()
