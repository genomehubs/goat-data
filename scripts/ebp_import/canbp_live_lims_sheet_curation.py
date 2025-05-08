#!/usr/bin/env python
# coding: utf-8
'''
description: script to get the target and status of the CANBP project from current LIMS system
'''

import pandas as pd
import numpy as np
import sys
import os

# Add the scripts directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import import_status_lib as isl

# original_link = https://docs.google.com/spreadsheets/d/1srUHdKEPrhL5ubQdhuEymetlM8oLpRPB2sSmxTvMIP4/edit?gid=1159288204#gid=1159288204
tsv_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRRLed7e4pcS6q24wbetDiVUaYXNWr5VjjVToUiSp4DMRSRmiv4HS1lHmRRVj51xXI3Sg24fqgwaJ2l/pub?gid=824666040&single=true&output=tsv'

# Select columns to import
used_columns= [
    "Scientific Name",
    "Common Name",
    "Status",
    "Summary",
    "taxid",
]

# Read the table from the link and create a column with the project name
canbp_list = pd.read_csv(tsv_link, sep='\t',
                         usecols=used_columns,
                         dtype=object)
canbp_list["project"] = "CANBP"

# Rename columns and clean up table using the import_status_lib functions

canbp_list = isl.general_cleanup_for_table(canbp_list)
canbp_list = isl.cleanup_headers_specific_units(canbp_list)

# Create a new column with the sequencing status and translate the values to the GoaT standard
canbp_list['sequencing_status'] = canbp_list['summary'].str.lower()

# Check unique values manually and compare with the translation in used. update the translation if needed

print(canbp_list["sequencing_status"].unique())
to_translate = {
                'data_generation, insdc_submitted': "data_generation",
                'paused': "sample_acquired",
                'resample needed, insdc_submitted': "resampling_required",
                'sample collected, insdc_submitted': "sample_acquired",
                'sample collected, paused': "sample_collected",
                }
canbp_list['sequencing_status'] = canbp_list['sequencing_status'].replace(to_translate)

# Create new columns with the status of the project and translate the values to the GoaT standard
# This function is equivalent to isl.create_status_column(canbp_list, "CANBP"), but adds resampling_required
# we are also fixing the problem of capitalization in the status column

def create_status_column(project_table, acronym):
    possible_seq_status = ["resampling_required","sample_collected","sample_acquired","in_progress","data_generation","in_assembly","insdc_submitted","open","insdc_open","published"]
    for item in possible_seq_status:   
        if item not in project_table:
            project_table[item] = np.nan
    #return project_table
    for item in possible_seq_status:        
        project_table.loc[project_table['sequencing_status'] == item.lower(), item] = acronym
    return project_table

# Create function that expands the status of the project based on the sequencing status, but also considering resampling_required
def expand_sequencing_status(project_table, acronym):
    project_table.loc[project_table["published"] == acronym, "insdc_open"] = acronym
    project_table.loc[project_table['insdc_open'] == acronym, 'open'] = acronym
    project_table.loc[project_table['open'] == acronym, 'insdc_submitted'] = acronym
    project_table.loc[project_table['insdc_submitted'] == acronym, 'in_assembly'] = acronym
    project_table.loc[project_table['in_assembly'] == acronym, 'data_generation'] = acronym
    project_table.loc[project_table['insdc_submitted'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['data_generation'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['in_assembly'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['in_progress'] == acronym, 'sample_acquired'] = acronym
    project_table.loc[project_table['sample_acquired'] == acronym, 'sample_collected'] = acronym
    return project_table

# Apply the new functions to the CANBP list and exprot the table
create_status_column(canbp_list, "CANBP")
expand_sequencing_status(canbp_list, "CANBP")
canbp_list.to_csv("CANBP_livestatus_expanded.tsv", sep="\t", index=False)
