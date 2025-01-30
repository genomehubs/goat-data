''''
Description:
This script reads the VGP Ordinal Phase1+ table and cleans it up for import into the GoaT database.
The script reads the table from a google spreadsheet link,
cleans up the table, and adds a project and status column to the table to conform to GoaT import.

'''
import pandas as pd
import numpy as np

# Google Spreadsheet link:
# https://docs.google.com/spreadsheets/d/1vsV7OTU-BAeOkBSrsESGCHaGuLcFW6U9mUluy6II0tY/edit?gid=0#gid=0
#Download link:
tsv_link = "https://docs.google.com/spreadsheets/d/1Jwjv6Kwc6VIn1UMMhnG6kvFCxjwGdC5b7p_HtbDOMOs/export?format=tsv&id=1Jwjv6Kwc6VIn1UMMhnG6kvFCxjwGdC5b7p_HtbDOMOs&gid=1380659438"

# Select colums to import
columns = [
    "Order",
    "Lineage",
    "Superorder",
    "Family Scientific Name",
    "Scientific Name",
    "English Name",
    "NCBI taxon ID",
    "Status",
    "QV",
    "IUCN (2016-2024)",
    "CITES",
    "Main project",
    "Second project",
    "Publication"
]
# Read the table from the link
vgp_df = pd.read_csv(tsv_link,
                    delimiter="\t",
                    dtype=object,
                    usecols=columns
                    )

print('Vgp file successfuly opened. Starting cleanup...')

def vgp_table_cleanup(df):
    """
    Cleans up a pandas DataFrame by performing the following actions:
    - Replaces empty or whitespace-only strings with NaN.
    - Strips leading and trailing spaces from all string values.
    - Drops columns and rows where all values are NaN.
    
    Args:
        df (pandas.DataFrame): The input DataFrame to be cleaned.

    Returns:
        pandas.DataFrame: The cleaned DataFrame.
    """
    df = df.replace(r'^\s*$', np.nan, regex=True)
    df = df.replace(r"^ +| +$", r"", regex=True)
    df.dropna(how="all", axis=1, inplace=True)
    df.dropna(how="all", axis=0, inplace=True)
    return df

def cleanup_vgp_headers_specific_units(df):
    """
    Cleans up the headers of a VGP table by performing the following actions:
    - Replaces spaces with underscores.
    - Converts all characters to lowercase.
    - Removes parentheses.

    Args:

        df (pandas.DataFrame): The input DataFrame to be cleaned.

    Returns:
        pandas.DataFrame: The cleaned DataFrame.
    """
    df.columns = (
        df.columns
        .str.replace(' ', '_')
        .str.replace(r'\(', '',regex=True)
        .str.replace(r'\)', '',regex=True)
        .str.lower()
    )
    return vgp_df

# Clean up the table:
vgp_df = vgp_table_cleanup(vgp_df)
vgp_df = cleanup_vgp_headers_specific_units(vgp_df)
print('Vgp file successfuly cleaned. Treating project columns...')

# Add a project column to the table
vgp_df["project"] = "VGP"

# Create a column with all projects working on the species

vgp_df['all_projects'] = vgp_df.apply(
    lambda row: ','.join(
        sorted(set(x for x in [row['project'], row['main_project'], row['second_project']] if pd.notna(x)))
    ),
    axis=1
)


# Translate the project names to acronyms when they are valid projects
# (needs manual update if new projects are added)
translate_to_acronyms = {
                            'Sanger 25G,VGP':'25GP,VGP',
                            'AfricaBP,VGP': 'AFRICABP,VGP', 
                            'Cetacean GP,VGP': 'CGP,VGP',
                            'VGP,Yggdrasil': 'VGP,YGG',
                            'CatalanBP,VGP': 'CBP,VGP',
                            'Canadian Biogenome Project,VGP': 'CANBP,VGP',
                            'Threatened Species Initiative (TSI),VGP': 'TSI,VGP',
                            'Canada Biogenome Project,VGP': 'CANBP,VGP',
                            'Minderoo OceanOmics,VGP': 'OG,VGP',
                            'Sanger 25G project,VGP': '25GP,VGP'
                        }

# Check for projects that need acronyms added using the following code
print(vgp_df['all_projects'].unique())
print('chech if any above should be translated to project acronym. Expanding status columns...')


# Map the acronyms to the project names in the all_projects column if they are in the translate_to_acronyms dictionary but leave the rest as is
vgp_df['all_projects'] = vgp_df['all_projects'].apply(
    lambda i: translate_to_acronyms[i] if i in translate_to_acronyms.keys() else i
)

possible_seq_status = ["sample_collected","sample_acquired","in_progress","data_generation","in_assembly","insdc_submitted","open","insdc_open","published"]
for item in possible_seq_status:
    if item not in vgp_df:
        vgp_df[item] = np.nan


# Map the status to the GoaT status
status_to_map = {
                '0': "",
                '1': "sample_collected",
                '2': "",
                '3': "in_progress",
                '4': "open",
                '5': "open",
                }

vgp_df['sequencing_status'] = vgp_df['status'].map(status_to_map)
# Map existing status for specific project combination to each status columns
for item in possible_seq_status:
    vgp_df.loc[vgp_df['sequencing_status'] == item, item] = vgp_df['all_projects']

# Populate the status columns with the project names using the hierarchy of the status
vgp_df.loc[vgp_df["published"] == vgp_df['all_projects'], "insdc_open"] = vgp_df['all_projects']
vgp_df.loc[vgp_df['insdc_open'] == vgp_df['all_projects'], 'open'] = vgp_df['all_projects']
vgp_df.loc[vgp_df['open'] == vgp_df['all_projects'], 'in_progress'] = vgp_df['all_projects']
vgp_df.loc[vgp_df['data_generation'] == vgp_df['all_projects'], 'in_progress'] = vgp_df['all_projects']
vgp_df.loc[vgp_df['in_assembly'] == vgp_df['all_projects'], 'in_progress'] = vgp_df['all_projects']
vgp_df.loc[vgp_df['in_progress'] == vgp_df['all_projects'], 'sample_acquired'] = vgp_df['all_projects']
vgp_df.loc[vgp_df['sample_acquired'] == vgp_df['all_projects'], 'sample_collected'] = vgp_df['all_projects']

print("Generating VGP_Ordinal_Phase1_plus.tsv file...")
vgp_df.to_csv("VGP_Ordinal_Phase1_plus.tsv",sep="\t", index=False)
