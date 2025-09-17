#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script fetches and combines GoaT reports to summarise available data
per country by taxon.
"""
import argparse
import os
import sys
from collections import defaultdict
from typing import List
from urllib.parse import quote

import requests
import yaml


def load_country_codes(
    file_path: str, country_field: str = "country_list"
) -> List[str]:
    """
    Load country codes from a file.
    """
    # country codes are the values in a YAML file with this structure:
    # attributes:
    #  country_list:
    #    constraint:
    #      enum:
    #        - af
    #        - al
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        sys.exit(1)

    # Parse the YAML file to extract country codes
    with open(file_path, "r") as file:
        data = yaml.safe_load(file)
        return sorted(
            data.get("attributes", {})
            .get(country_field, {})
            .get("constraint", {})
            .get("enum", [])
        )


def group_country_codes(
    country_codes: List[str], group_size: int = 10
) -> List[List[str]]:
    """
    Group country codes into chunks of a specified size.
    """
    return [
        country_codes[i : i + group_size]
        for i in range(0, len(country_codes), group_size)
    ]


def build_query_string(
    root_taxon: str,
    modifier: str,
    count_rank: str,
    group_rank: str,
    country_field: str,
    country_codes: str = "",
) -> str:
    """
    Build a query string for the GoaT API.
    """
    query = [
        f"tax_tree({root_taxon})",
        f"tax_rank({count_rank})",
        f"{country_field}={country_codes}" if country_codes else country_field,
    ]
    if modifier:
        query.append(modifier)
    query_str = quote(" AND ".join(query))
    fields = [
        "ebp_standard_criteria",
        "assembly_level",
        country_field,
    ]
    fields_str = quote(",".join(fields))
    return (
        f"query={query_str}&result=taxon&includeEstimates=true&"
        f"taxonomy=ncbi&fields={fields_str}&"
        f"ranks={group_rank}"
    )


def count_groups(
    base_url: str,
    root_taxon: str,
    modifier: str,
    group_rank: str,
    country_field: str,
) -> int:
    """
    Count the number of using GoaT API /count endpoint.
    """
    query_string = build_query_string(
        root_taxon, modifier, group_rank, group_rank, country_field
    )
    url = f"{base_url}/count?{query_string}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error fetching data from {url}: {response.status_code}")
        sys.exit(1)

    data = response.json()
    return data.get("count", 0)


def build_report_urls(
    country_codes: List[str],
    base_url: str,
    root_taxon: str,
    modifier: str,
    count_rank: str,
    group_rank: str,
    country_field: str,
    max_bins: int = 2500,
) -> List[str]:
    """
    Build URLs for the GoaT API to fetch reports.
    """
    group_count = count_groups(
        base_url, root_taxon, modifier, group_rank, country_field
    )
    if group_count > max_bins:
        print(
            f"Warning: The number of groups ({group_count}) exceeds the maximum "
            f"allowed ({max_bins}). Some groups may not be included in the report."
        )
    grouped_country_codes = group_country_codes(
        country_codes, int(max_bins // group_count)
    )
    # Build a URL for all countries combined
    xOpts = quote("1;1000000000000;2")
    query_string = build_query_string(
        root_taxon, modifier, count_rank, group_rank, country_field, ""
    )
    query_string = query_string.replace("query=", "x=assembly_span%20AND%20")
    url = (
        f"{base_url}/report?{query_string}&"
        f"report=table&rank={count_rank}&"
        f"cat={group_rank}[{group_count}]&"
        f"xOpts={xOpts}&compactLegend=true"
    )
    urls = [url]
    # Build per country URLs
    for group in grouped_country_codes:
        group_str = ",".join(group)
        xOpts = quote(f"{group_str};;{len(group)}")
        query_string = build_query_string(
            root_taxon, modifier, count_rank, group_rank, country_field, group_str
        )
        query_string = query_string.replace("query=", "x=")

        # Build the URL for each group of country codes
        url = (
            f"{base_url}/report?{query_string}&"
            f"report=table&rank={count_rank}&"
            f"cat={group_rank}[{group_count}]&"
            f"xOpts={xOpts}&compactLegend=true"
        )
        urls.append(url)

    return urls


def update_translate_keys(translate_keys: dict, new_keys: list) -> None:
    """
    Update the translate keys dictionary with new keys.

    This function merges new keys into the existing translate keys dictionary.
    """
    for entry in new_keys:
        key = entry.get("key", None)
        label = entry.get("label", None)
        if key is None or label is None:
            continue
        if key not in translate_keys:
            translate_keys[key] = label


def parse_reports(urls: List[str]) -> dict:
    """
    Parse the reports from the provided URLs.

    This function creates a single dictionary summarizing all reports
    """
    translate_keys = {}
    all_buckets = []
    results = defaultdict(lambda: defaultdict(int))
    for url in urls:
        print(f"Fetching data from: {url}")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching data from {url}: {response.status_code}")
            continue

        data = response.json()
        if not data:
            print(f"No data found for URL: {url}")
            continue

        if not data.get("status", {}).get("success", False):
            print(
                (
                    f"Error in response for URL {url}: "
                    f"{data.get('status', {}).get('error', 'Unknown error')}"
                )
            )
            continue

        table = data.get("report", {}).get("report", {}).get("table", {})
        update_translate_keys(translate_keys, table.get("cats", []))

        buckets = [
            bucket
            for bucket in table.get("histograms", {}).get("buckets", [])
            if bucket is not None
        ]
        all_buckets.extend(buckets)
        allValues = table.get("histograms", {}).get("allValues", [])
        byCat = table.get("histograms", {}).get("byCat", {})
        for idx, bucket in enumerate(buckets):
            results[bucket]["TOTAL"] = allValues[idx]
        for cat, values in byCat.items():
            for idx, bucket in enumerate(buckets):
                results[bucket][cat] = values[idx]
    return {
        "translate_keys": translate_keys,
        "results": results,
    }


def write_results_to_csv(
    results: list, group_rank: str, modifiers: list, translate_keys: dict, outfile: str
) -> None:
    """
    Write the results to a CSV file.
    """

    with open(outfile, "w", newline="") as csvfile:
        fieldnames = ["country_code", group_rank] + [
            modifier or "all" for modifier in modifiers
        ]
        csvfile.write(",".join(fieldnames) + "\n")
        for country_code, values in results[0].items():
            for key, value in values.items():
                translated_key = translate_keys.get(key, key)
                try:
                    row = [country_code.upper(), translated_key]
                except AttributeError:
                    if str(country_code) == "1":
                        row = ["TOTAL", translated_key]
                    else:
                        continue
                for idx, _ in enumerate(modifiers):
                    if idx == 0:
                        row.append(str(value))
                    else:
                        row.append(str(results[idx].get(country_code, {}).get(key, 0)))
                csvfile.write(",".join(row) + "\n")


def parse_args() -> str:
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate IPBES reports and URLs based on GoaT data."
    )
    parser.add_argument(
        "country_codes_file",
        type=str,
        help="Path to the YAML file containing country codes.",
    )
    parser.add_argument(
        "--country-field",
        dest="country_field",
        type=str,
        default="country_list",
        help="Field that contains the list of country codes (default: 'country_list').",
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        type=str,
        default="https://goat.genomehubs.org/api/v2",
        help="Base URL for the GoaT API.",
    )
    parser.add_argument(
        "--root-taxon",
        dest="root_taxon",
        type=str,
        default="2759[Eukaryota]",
        help=(
            "Name or taxID of the root taxon to use in the reports "
            "(default: '2759[Eukaryota]')."
        ),
    )
    parser.add_argument(
        "--modifiers",
        dest="modifiers",
        nargs="*",
        type=str,
        default=[],
        help=(
            "List of modifiers to append to the base query URL "
            "(e.g., --modifiers '?format=json' '&limit=100')."
        ),
    )
    parser.add_argument(
        "--count-rank",
        dest="count_rank",
        type=str,
        default="species",
        help="Taxon rank to count in the reports (default: 'species').",
    )
    parser.add_argument(
        "--group-rank",
        dest="group_rank",
        type=str,
        default="class",
        help="Taxon rank to group by in the reports (default: 'class').",
    )
    parser.add_argument(
        "--max-bins",
        dest="max_bins",
        type=int,
        default=2500,
        help=(
            "Maximum number of bins to use for country code/taxon groups "
            "(default: 2500). This is used to limit the number of groups "
            "when generating URLs."
        ),
    )
    parser.add_argument(
        "--outfile",
        dest="outfile",
        type=str,
        default="ipbes_reports.csv",
        help=(
            "Output file to save the generated report URLs and results "
            "(default: 'ipbes_reports.csv')."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load country codes from the specified file
    country_codes = load_country_codes(args.country_codes_file, args.country_field)

    # Build report URLs based on the provided parameters
    modifiers = args.modifiers or [""]
    if "" not in modifiers:
        modifiers.insert(0, "")

    result_sets = []
    translate_keys = {}

    for idx, modifier in enumerate(modifiers):
        modifier = modifier.strip()
        urls = build_report_urls(
            country_codes,
            args.base_url,
            args.root_taxon,
            modifier,
            args.count_rank,
            args.group_rank,
            args.country_field,
            args.max_bins,
        )

        output = parse_reports(urls)
        if idx == 0:
            translate_keys = output.get("translate_keys", {})
        result_sets.append(output.get("results", {}))

    # Write the results to a CSV file
    write_results_to_csv(
        result_sets,
        args.group_rank,
        modifiers,
        translate_keys,
        args.outfile,
    )


if __name__ == "__main__":
    main()
    sys.exit(main())


# This script can be called as, e.g.:
# python scripts/ipbes_reports.py sources/regional-lists/ATTR_regional_list.types.yaml \
#     --max-bins 2500 \
#     --modifiers 'assembly_level' 'ebp_standard_criteria' \
#     --outfile goat_ipbes_report_order.csv \
#     --group-rank order \
#     --root-taxon '32523[Tetrapoda]'

# python scripts/ipbes_reports.py sources/regional-lists/ATTR_regional_list.types.yaml \
#     --max-bins 2500 \
#     --modifiers 'assembly_level' 'ebp_standard_criteria' \
#     --outfile goat_ipbes_report_class.csv \
#     --group-rank class \
#     --root-taxon '2759[Eukaryota]'
