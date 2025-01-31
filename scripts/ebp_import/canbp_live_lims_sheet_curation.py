#!/usr/bin/env python
# coding: utf-8
'''
description: script to get the target and status of the CANBP project from current LIMS system
'''

import pandas as pd
import numpy as np
import import_status_lib as isl

# original_link = https://docs.google.com/spreadsheets/d/1srUHdKEPrhL5ubQdhuEymetlM8oLpRPB2sSmxTvMIP4/edit?gid=824666040#gid=824666040
tsv_link = 'https://urldefense.proofpoint.com/v2/url?u=https-3A__docs.google.com_spreadsheets_d_e_2PACX-2D1vRRLed7e4pcS6q24wbetDiVUaYXNWr5VjjVToUiSp4DMRSRmiv4HS1lHmRRVj51xXI3Sg24fqgwaJ2l_pub-3Fgid-3D824666040-26single-3Dtrue-26output-3Dtsv&d=DwMF_w&c=D7ByGjS34AllFgecYw0iC6Zq7qlm8uclZFI0SqQnqBo&r=ROFPW9s86BDaHzmK9wYUbmvRhmF6aEC2Q3PZs5L7P9o&m=WdCSKek56V9LCJWgkihfRJ1NMeTCn-E15wULx9ksI_f4oPMLtXCgBpJgVUq_sazC&s=Q249FQQa_Jfd0GEfQJTjNwG3bwCDnVfwPbaYXlX1WHs&e='

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
canbp_list.to_csv("CANBP_status_expanded.tsv", sep="\t", index=False)
