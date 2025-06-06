import numpy as np
import pandas as pd
import os

# Helper function to handle file reading with error handling
def safe_read_csv(file_path, delimiter="\t", **kwargs):
    try:
        return pd.read_csv(file_path, delimiter=delimiter, **kwargs)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return pd.DataFrame()

# Open private TSV file
def open_private_tsv(private_link_token):
    return safe_read_csv(
        private_link_token,
        usecols=["project_acronym", "published_url", "start_header_line"],
        dtype=object,
    )

# Open public TSV file
def open_public_tsv(public_url):
    return safe_read_csv(
        public_url,
        usecols=["project_acronym", "published_url", "start_header_line"],
        dtype=object,
    )

# Open Google Spreadsheet
def open_google_spreadsheet(acronym, file_link, header_index):
    encodings = ['utf-8', 'ISO-8859-1', 'latin1']  # List of encodings to try
    project_table = None
    
    for encoding in encodings:
        try:
            project_table = pd.read_csv(
                file_link,
                delimiter="\t",
                header=header_index,
                dtype=object,
                quoting=3,
                encoding=encoding
            )
            print(f"File opened successfully with {encoding} encoding.")
            break  # Exit the loop if reading is successful
        except UnicodeDecodeError:
            print(f"Failed to open file with {encoding} encoding. Trying next...")

    if project_table is None:
        raise ValueError("Failed to open the file with the provided encodings.")

    project_table.rename(columns={"#NCBI_taxon_id": "NCBI_taxon_id"}, inplace=True)
    project_table["project"] = acronym.upper()
    return project_table

# General cleanup for table
def general_cleanup_for_table(project_table):
    project_table = project_table.replace(r"^\s*$", np.nan, regex=True).infer_objects(copy=False)
    project_table = project_table.replace(r"^ +| +$", "", regex=True)
    project_table.replace("publication_available", "published", inplace=True)
    project_table.replace("-", "", inplace=True)
    project_table.dropna(how="all", axis=1, inplace=True)
    project_table.dropna(how="all", axis=0, inplace=True)
    project_table.rename(columns={"#NCBI_taxon_id": "NCBI_taxon_id"}, inplace=True)
    return project_table

# Cleanup headers
def cleanup_headers_specific_units(project_table):
    project_table.columns = (
        project_table.columns
        .str.replace(" ", "_")
        .str.replace("\\(", "", regex=True)
        .str.replace("\\)", "", regex=True)
        .str.lower()
    )
    return project_table

# Expand target status
def expand_target_status(project_table, acronym):
    possible_target_status = ["long_list", "family_representative", "other_priority"]
    
    # Initialize columns as object dtype
    for item in possible_target_status:
        if item not in project_table:
            project_table[item] = pd.Series(dtype="object")
    
    project_table["long_list"] = acronym

    project_table.loc[
        project_table["target_list_status"] == acronym.lower() + "_family_representative",
        "family_representative",
    ] = acronym

    project_table.loc[
        project_table["target_list_status"] == acronym.lower() + "_other_priority",
        "other_priority",
    ] = acronym

    project_table.loc[
        project_table["target_list_status"] == "family_representative",
        "family_representative",
    ] = acronym
    
    project_table.loc[
        project_table["target_list_status"] == "other_priority", "other_priority"
    ] = acronym

    return project_table

# Reduce sequencing status
def reduce_sequencing_status(project_table, acronym):
    acronym_lower = acronym.lower()
    status_mapping = {
        f"{acronym_lower}_published": "published",
        f"{acronym_lower}_insdc_open": "insdc_open",
        f"{acronym_lower}_open": "open",
        f"{acronym_lower}_insdc_submitted": "in_progress",
        f"{acronym_lower}_in_assembly": "in_progress",
        f"{acronym_lower}_data_generation": "in_progress",
        f"{acronym_lower}_in_progress": "in_progress",
        f"{acronym_lower}_sample_acquired": "sample_acquired",
        f"{acronym_lower}_sample_collected": "sample_collected",
    }
    project_table["sequencing_status"].replace(status_mapping, inplace=True)
    return project_table

# Create status columns
def create_status_column(project_table, acronym):
    possible_seq_statuses = [
        "sample_collected", "sample_acquired", "in_progress", "data_generation",
        "in_assembly", "insdc_submitted", "open", "insdc_open", "published",
    ]

    for status in possible_seq_statuses:
        if status not in project_table:
            project_table[status] = pd.Series(dtype="object")

    for status in possible_seq_statuses:
        project_table[status] = project_table[status].astype(object)
        project_table.loc[project_table["sequencing_status"] == status, status] = acronym
    return project_table

# Expand sequencing status
def expand_sequencing_status(project_table, acronym):
    project_table.loc[project_table["published"] == acronym, "insdc_open"] = acronym
    project_table.loc[project_table["insdc_open"] == acronym, "open"] = acronym
    project_table.loc[project_table["open"] == acronym, "in_progress"] = acronym
    project_table.loc[
        project_table["data_generation"] == acronym, "in_progress"
    ] = acronym
    project_table.loc[project_table["in_assembly"] == acronym, "in_progress"] = acronym
    project_table.loc[
        project_table["in_progress"] == acronym, "sample_acquired"
    ] = acronym
    project_table.loc[
        project_table["sample_acquired"] == acronym, "sample_collected"
    ] = acronym
    return project_table

# Expand sequencing status Remastered
def expand_sequencing_status_new(project_table, acronym):
    project_table.loc[project_table["published"] == acronym, "insdc_open"] = acronym
    project_table.loc[project_table["insdc_open"] == acronym, "open"] = acronym
    project_table.loc[project_table["open"] == acronym, "in_progress"] = acronym
    project_table.loc[
        project_table["data_generation"] == acronym, "in_progress"
    ] = acronym
    project_table.loc[project_table["in_assembly"] == acronym, "in_progress"] = acronym
    project_table.loc[
        project_table["in_progress"] == acronym, "sample_acquired"
    ] = acronym
    project_table.loc[
        project_table["sample_acquired"] == acronym, "sample_collected"
    ] = acronym
    return project_table

# Create mandatory columns
def create_mandatory_columns(project_table):
    mandatory_fields = [
        "ncbi_taxon_id", "species", "family", "synonym",
        "publication_id", "contributing_project_lab",
    ]

    for field in mandatory_fields:
        if field not in project_table:
            project_table[field] = np.nan
    return project_table

# Export TSV file
def export_expanded_tsv(project_table, acronym):
    """
    Save the file to the "tsv" folder in the same directory as the scripts.
    
    """
    file_name = f"tsv/{acronym}_expanded.tsv" 
    return project_table.to_csv(file_name, sep="\t", index=False)

# Full processing pipeline for spreadsheets
def processing_schema_2_5_lists(acronym, url, start_row):
    print(f"Opening {acronym} URL...")
    project_table = open_google_spreadsheet(acronym, url, start_row)
    print(f"Cleaning up {acronym} table...")
    project_table = general_cleanup_for_table(project_table)
    project_table = cleanup_headers_specific_units(project_table)
    print(f"Expanding {acronym} target status...")
    project_table = expand_target_status(project_table, acronym)
    project_table = create_status_column(project_table, acronym)
    print(f"Expanding {acronym} sequencing status...")
    project_table = expand_sequencing_status(project_table, acronym)
    print(f"creating {acronym} mandatory fields ...")
    project_table = create_mandatory_columns(project_table)
    print(f"Saving {acronym} to file...")
    export_expanded_tsv(project_table, acronym)






