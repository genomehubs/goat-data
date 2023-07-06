import numpy as np
import pandas as pd

def open_private_tsv(private_link_token):
    private_tsv = pd.read_csv(private_link_token
                             ,delimiter="\t"
                             ,usecols=["project_acronym","published_url","start_header_line"]
                             ,dtype=object
                             )
    return private_tsv

def open_google_spreadsheet(acronym, file_link, header_index):
    project_table = pd.read_csv(file_link,
                    # Set first column as rownames in data frame
                    delimiter="\t", header=header_index, dtype=object
                    )
    project_table.rename(columns={'#NCBI_taxon_id':'NCBI_taxon_id'}, inplace=True)
    project_table["project"] = acronym.upper()
    return project_table


def general_cleanup_for_table(project_table):
    project_table = project_table.replace(r'^\s*$', np.nan, regex=True)
    project_table.dropna(how="all", axis=1, inplace=True)
    project_table.dropna(how="all", axis=0, inplace=True)
    project_table.rename(columns={'#NCBI_taxon_id':'NCBI_taxon_id'}, inplace=True)
    return project_table

# Cleanup headers
def cleanup_headers_specific_units(project_table):
    project_table.columns = (
        project_table.columns
        .str.replace(' ', '_')
        .str.replace('\(', '')
        .str.replace('\)', '')
        .str.lower()
    )
    return project_table

# Create and Populate target status columns

def expand_target_status(project_table, acronym):
    possible_target_status = ["long_list","family_representative","other_priority"]
    for item in possible_target_status:
        if item not in project_table:
         project_table[item] = np.nan
    project_table['long_list'] = acronym
    project_table.loc[project_table['target_list_status'] == acronym.lower() + '_family_representative', 'family_representative'] = acronym
    project_table.loc[project_table['target_list_status'] == acronym.lower() + '_other_priority', 'other_priority'] = acronym
    project_table.loc[project_table['target_list_status'] == 'family_representative', 'family_representative'] = acronym
    project_table.loc[project_table['target_list_status'] == 'other_priority', 'other_priority'] = acronym
    return project_table


# Convert long version of status to simple GoaT status (not really necessary)
def reduce_sequencing_status(project_table, acronym):
    status_to_map = {acronym + '_published':'published',
                     acronym + '_insdc_open':'insdc_open',
                     acronym + '_open':'open',
                     acronym + '_insdc_submitted':'in_progress',
                     acronym + '_in_assembly':'in_progress',
                     acronym + '_data_generation':'in_progress',
                     acronym + '_in_progress':'in_progress',
                     acronym + '_sample_acquired':'sample_acquired',
                     acronym + '_sample_collected':'sample_collected'
                    }
    project_table['sequencing_status'].replace(status_to_map, inplace=True)
    return project_table

# Short version of the above 
# Problem: the command itself works, but when called as a function it does not

def remove_acronym_prefix(project_table):
    project_table['target_list_status'].str.split('_').str[1:].str.join('_') 
    return project_table

# Exploring this further:
# import pandas as pd
# test = pd.DataFrame(
#     {
#         'column with spaces': [1,2,3],
#         'column with units (unit)' : [4,5,6]
#     }
# )
#
# test.columns.str.replace(' ', '_').str.replace('\(', '').str.replace('\)', '')

# Expand sequencing status into columns:

def create_status_column(project_table, acronym):
    possible_seq_status = ["sample_collected","sample_acquired","in_progress","data_generation","in_assembly","insdc_submitted","open","insdc_open","published"]
    for item in possible_seq_status:   
        if item not in project_table:
            project_table[item] = np.nan
    #return project_table
    for item in possible_seq_status:        
        project_table.loc[project_table['sequencing_status'] == item, item] = acronym
    return project_table

def expand_sequencing_status(project_table, acronym):
    project_table.loc[project_table['insdc_open'] == acronym, 'open'] = acronym
    project_table.loc[project_table['open'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['data_generation'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['in_assembly'] == acronym, 'in_progress'] = acronym
    project_table.loc[project_table['in_progress'] == acronym, 'sample_acquired'] = acronym
    project_table.loc[project_table['sample_acquired'] == acronym, 'sample_collected'] = acronym
    return project_table

# Export tsv:

def export_expanded_tsv(project_table, acronym):
    file_name = './sources/status_lists/' + acronym + '_expanded.tsv'
    final_tsv = project_table.to_csv(file_name, sep="\t", index=False)
    return final_tsv


# Putting all together for standard GoaT spreadsheets, schema 2.5
import import_status_lib as isl

def processing_schema_2_5_lists(acronym,url,start_row):
    print(f'opening {acronym} url ...')
    project_table = isl.open_google_spreadsheet(acronym,url,start_row)
    print(f'cleaning up {acronym} table ...')
    project_table = isl.general_cleanup_for_table(project_table)
    project_table = isl.cleanup_headers_specific_units(project_table)
    print(f'expanding {acronym} target status ...')
    project_table = isl.expand_target_status(project_table, acronym)
    project_table = isl.create_status_column(project_table, acronym)
    print(f'expanding {acronym} sequencing status ...')
    project_table = isl.expand_sequencing_status(project_table, acronym)
    print(f'saving {acronym} to file')
    isl.export_expanded_tsv(project_table, acronym)


