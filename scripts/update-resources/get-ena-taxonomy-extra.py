#!/usr/bin/env python3

# This script replaces the get_ena_taxonomy_extra.bash script
# It uses the ENA API to get taxonomy information for additional taxa not included in
# the taxdump file at https://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz.

import gzip
import os
import re
import sys
from urllib.request import urlopen


def get_taxonomy_ids(taxroot):
    url = "https://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz"
    print(f"Fetching taxdump file from {url}")

    streamed_file = urlopen(url)
    with gzip.GzipFile(fileobj=streamed_file) as f_in:
        with open("ena-taxonomy.xml.taxids", "w") as f_out:
            for line in f_in:
                if tax_id := re.search(r'taxId="(\d+)"', line.decode("utf-8")):
                    f_out.write(f"{tax_id[1]}\n")


def get_ena_api_taxids(taxroot):
    print(f"Fetching full list of taxids for tax_tree({taxroot}) from ENA API")

    taxdump_ids = set()
    with open("ena-taxonomy.xml.taxids") as f_in:
        for line in f_in:
            taxdump_ids.add(line.strip())

    limit = 10000000
    url = (
        f"https://www.ebi.ac.uk/ena/portal/api/search?result=taxon"
        f"&query=tax_tree({taxroot})&limit={limit}"
    )
    output_file = f"resulttaxon.tax_tree{taxroot}.taxids"

    # Stream the content of the URL and print text line by line
    column_index = None
    tax_ids = set()
    with urlopen(url) as response, open(output_file, "w") as f_out:
        for line in response:
            columns = line.decode("utf-8").strip().split("\t")
            if column_index is None:
                column_index = 0 if columns[0] == "tax_id" else 1
            else:
                f_out.write(columns[column_index] + "\n")
                tax_ids.add(columns[column_index])
    return tax_ids - taxdump_ids


def get_new_ids(all_tax_ids):
    print("Checking for new tax_ids")
    existing_tax_ids = set()
    if os.path.exists("ena-taxonomy.extra.jsonl.gz"):
        with gzip.open("ena-taxonomy.extra.jsonl.gz", "rt") as f_in, gzip.open(
            "ena-taxonomy.prev.jsonl.gz", "wt"
        ) as f_out:
            for line in f_in:
                if tax_id := re.search(r'"taxId"\s*:\s*"(\d+)"', line):
                    existing_tax_ids.add(tax_id[1])
                    if tax_id[1] in all_tax_ids:
                        f_out.write(line)

    new_tax_ids = all_tax_ids - existing_tax_ids
    with open("new_tax_ids.txt", "w") as f_out:
        for tax_id in new_tax_ids:
            f_out.write(f"{tax_id}\n")

    return new_tax_ids


def fetch_new_taxa_jsonl(new_tax_ids):
    print("Fetching new tax_ids from ENA API")
    url = "https://www.ebi.ac.uk/ena/taxonomy/rest/tax-id/"
    with gzip.open("ena-taxonomy.new.jsonl.gz", "at") as f_out:
        count = len(new_tax_ids)
        for ctr, tax_id in enumerate(new_tax_ids):
            if ctr % 1000 == 0:
                print(f"Downloaded {ctr} of {count} tax_ids")
            with urlopen(url + tax_id) as response:
                for line in response:
                    f_out.write(line.decode("utf-8").strip())
                f_out.write("\n")


if __name__ == "__main__":
    taxroot = sys.argv[1] if len(sys.argv) > 1 else "2759"
    get_taxonomy_ids(taxroot)
    all_tax_ids = get_ena_api_taxids(taxroot)
    new_tax_ids = get_new_ids(all_tax_ids)
    print(f"New tax_ids: {len(new_tax_ids)}")
    fetch_new_taxa_jsonl(new_tax_ids)
