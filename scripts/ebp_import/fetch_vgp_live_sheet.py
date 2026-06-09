#!/usr/bin/env python
# coding: utf-8

# Description:This script reads the VGP Ordinal Phase1+ table and saves it to a tsv file for further cleanup before importing into the GoaT database.

import pandas as pd
import numpy as np

# Google Spreadsheet link:
# https://docs.google.com/spreadsheets/d/1vsV7OTU-BAeOkBSrsESGCHaGuLcFW6U9mUluy6II0tY/edit?gid=0#gid=0
#Download link:
tsv_link = "https://docs.google.com/spreadsheets/d/1Jwjv6Kwc6VIn1UMMhnG6kvFCxjwGdC5b7p_HtbDOMOs/export?format=tsv&id=1Jwjv6Kwc6VIn1UMMhnG6kvFCxjwGdC5b7p_HtbDOMOs&gid=1380659438"


# Fetch the table from the link and export it as a tsv file as is

def fetch_vgp_table(tsv_link, output_path):
    """
    Fetches the VGP table from the provided Google Sheets link and saves it as a TSV file.

    Args:
        tsv_link (str): The URL to the Google Sheets TSV export.
        output_path (str): The file path where the TSV should be saved.
    """
    vgp_df = pd.read_csv(
    tsv_link,
    sep="\t",
    dtype=object,
    engine="python",
    on_bad_lines="warn"  # or "skip"
)
    vgp_df.to_csv(output_path, sep="\t", index=False)
    print(f"VGP table fetched and saved to {output_path}")

if __name__ == "__main__":
    output_path = "vgp_ordinal_phase1_plus.tsv"
    fetch_vgp_table(tsv_link, output_path)      




