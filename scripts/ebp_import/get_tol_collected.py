''''
This script will edit all files used by DToL samples working groups 
Goal is to transform original files into tsvs for GoaT import
'''

import import_status_lib as isl
import numpy as np


#DTOL Arthropoda Family Representatives
# DToL live sheet as of Nov 2024:
# https://docs.google.com/spreadsheets/d/10-RSLWo-0Hn0Lx3z_WJYuvx0WcgrlokFhqUpq4byJEc/edit?pli=1#gid=1370114100
# public tsv:
# https://docs.google.com/spreadsheets/d/e/2PACX-1vR6BXo-Z8cGMoMuREw4qt1rIqwf1wY4rRlfPw2ehKspPe_l8Gn5xb6rHwZOp26FgThBaszDyarKhHfi/pub?gid=1370114100&single=true&output=tsv

#### Open dataframe and add file-specific edits to clean file contents
DTOL_AFR = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/e/2PACX-1vR6BXo-Z8cGMoMuREw4qt1rIqwf1wY4rRlfPw2ehKspPe_l8Gn5xb6rHwZOp26FgThBaszDyarKhHfi/pub?gid=1370114100&single=true&output=tsv",0)
DTOL_AFR = DTOL_AFR.replace(r'^\s*$', np.nan, regex=True)
DTOL_AFR.dropna(subset=['SPECIES'], axis=0, inplace=True)
DTOL_AFR.drop(DTOL_AFR.loc[DTOL_AFR['SPECIES']=="NA"].index, axis=0, inplace=True)
DTOL_AFR["long_list"],DTOL_AFR["family_representative"] = ["DTOL","DTOL"]


# Add column for sample_collected
DTOL_AFR.loc[DTOL_AFR['COPO'] == "COLLECTED", 'sample_collected'] = "DTOL"
DTOL_AFR.loc[DTOL_AFR['NHM'] == "COLLECTED", 'sample_collected'] = "DTOL"
DTOL_AFR.loc[DTOL_AFR['WYTHAM'] == "COLLECTED", 'sample_collected'] = "DTOL"
DTOL_AFR.loc[DTOL_AFR['TOL_SCOTLAND'] == "COLLECTED", 'sample_collected'] = "DTOL"

# Replace values in each respective columns for NHM, WW and TOL-Scotland
DTOL_AFR['NHM'] = DTOL_AFR['NHM'].replace("COLLECTED",'NHM')
DTOL_AFR['WYTHAM'] = DTOL_AFR['WYTHAM'].replace("COLLECTED",'WW')
DTOL_AFR['TOL_SCOTLAND'] = DTOL_AFR['TOL_SCOTLAND'].replace("COLLECTED",'SAN')

# Export edited tsvs
isl.export_expanded_tsv(DTOL_AFR, "DTOL_Arthropoda_family_reps")


#####
#DTOL Bryophyte Collections
# DToL live sheet as of Nov 2024:
# https://docs.google.com/spreadsheets/d/10-RSLWo-0Hn0Lx3z_WJYuvx0WcgrlokFhqUpq4byJEc/edit?pli=1#gid=1370114100
# published tsv: 
# https://docs.google.com/spreadsheets/d/e/2PACX-1vSWzz8Sut3hQFB4DyxYE_wiZZrHB41VXokc8eihEGAOKdMPDhGw2KkJIl-zjAob6oeDcqgri1zcF3d8/pub?gid=0&single=true&output=tsv

DTOL_Bryophytes = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/e/2PACX-1vSWzz8Sut3hQFB4DyxYE_wiZZrHB41VXokc8eihEGAOKdMPDhGw2KkJIl-zjAob6oeDcqgri1zcF3d8/pub?gid=0&single=true&output=tsv",0)
DTOL_Bryophytes = isl.general_cleanup_for_table(DTOL_Bryophytes)
DTOL_Bryophytes = isl.cleanup_headers_specific_units(DTOL_Bryophytes)

# Export edited tsvs
isl.export_expanded_tsv(DTOL_Bryophytes, "DTOL_Bryophytes_collected")

#####
#DTOL Land Plants Collections
# DToL live sheet as of Nov 2024:
# https://docs.google.com/spreadsheets/d/1PUCMzq706yxhZvJbeYW1pZ0C8nBaRgNgTXCH3o3AqAw/edit#gid=0
# Download tsv link:https://docs.google.com/spreadsheets/d/1PUCMzq706yxhZvJbeYW1pZ0C8nBaRgNgTXCH3o3AqAw/export?format=tsv&id=1PUCMzq706yxhZvJbeYW1pZ0C8nBaRgNgTXCH3o3AqAw&gid=0
# published tsv:

DTOL_Vascular = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/1PUCMzq706yxhZvJbeYW1pZ0C8nBaRgNgTXCH3o3AqAw/export?format=tsv&id=1PUCMzq706yxhZvJbeYW1pZ0C8nBaRgNgTXCH3o3AqAw&gid=0",0)
DTOL_Vascular = isl.general_cleanup_for_table(DTOL_Vascular)
DTOL_Vascular = isl.cleanup_headers_specific_units(DTOL_Vascular)

# Export edited tsvs
isl.export_expanded_tsv(DTOL_Vascular, "DTOL_Vascular_collected")

#####
#DTOL Fungi
# DToL live sheet as of Jan 2025: https://docs.google.com/spreadsheets/d/1c0uHM38Y0by8En2u7NrUknZ528Nc8Z9I/edit?gid=1328394438#gid=1328394438
# published tsv: https://docs.google.com/spreadsheets/d/e/2PACX-1vTJx34F3epA5-PwStWqvHLm_eemyCOreW_vOBWGZ9TlS8CZ9ytf3nsMBKeJS8dZYQ/pub?gid=1328394438&single=true&output=tsv

DTOL_Fungi = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/e/2PACX-1vTJx34F3epA5-PwStWqvHLm_eemyCOreW_vOBWGZ9TlS8CZ9ytf3nsMBKeJS8dZYQ/pub?gid=1328394438&single=true&output=tsv",0)
DTOL_Fungi = isl.general_cleanup_for_table(DTOL_Fungi)
DTOL_Fungi = isl.cleanup_headers_specific_units(DTOL_Fungi)

# Export edited tsvs
isl.export_expanded_tsv(DTOL_Fungi, "DTOL_Fungi_collected")


#####
#DTOL Protists

dtol_protist = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/e/2PACX-1vQOZv_it6Wa1i3l54sZgMR2w38Me_Zlbmfq81YlGEhKHmOX5HYg213yn1-97Py_qA/pub?gid=1818735230&single=true&output=tsv",0)
dtol_protist = isl.cleanup_headers_specific_units(dtol_protist)
dtol_protist = isl.general_cleanup_for_table(dtol_protist)

prot_status_to_map = {
    'COLLECTED': 'sample_collected',
    'SUBMITTED':'sample_collected',
    'RESUBMITTED':'sample_collected',
    'GROWING':'sample_collected',
    'DEAD': ""
}
dtol_protist['sample_collected'] = dtol_protist['status'].map(prot_status_to_map)
isl.export_expanded_tsv(dtol_protist, "DTOL_protist_collected")

#####
#DTOL Chordata
# https://docs.google.com/spreadsheets/d/1on84bBNxuUG5jouh4tb7clb5EQ2bvU5Z-o_wFyJg9VA/edit?gid=1707413927#gid=1707413927
# published tsv: 'https://docs.google.com/spreadsheets/d/e/2PACX-1vR35J07MSypi_jSOgX9Jxe7RIAo56NiI12esouj9jccdvjNxPV1-Hg5Idfk_1Zb0kQgiYrzNAC7Qjz3/pub?gid=1707413927&single=true&output=tsv'

chordate_collected = isl.open_google_spreadsheet("DTOL","https://docs.google.com/spreadsheets/d/e/2PACX-1vR35J07MSypi_jSOgX9Jxe7RIAo56NiI12esouj9jccdvjNxPV1-Hg5Idfk_1Zb0kQgiYrzNAC7Qjz3/pub?gid=1707413927&single=true&output=tsv",0)
chordate_collected = isl.general_cleanup_for_table(chordate_collected)
chordate_collected = isl.cleanup_headers_specific_units(chordate_collected)

isl.export_expanded_tsv(chordate_collected, "DTOL_chordata_collected")


#####
#PSYCHE
# Psyche working_species_collection_list
# https://docs.google.com/spreadsheets/d/1cGhiZwdWqHdeZaLW9eZDhL4jWbw-pr1nKV_akA66Ha8/edit?gid=1962198900#gid=1962198900
# published tsv: https://docs.google.com/spreadsheets/d/e/2PACX-1vT8AnakXtq3aTsVu48SRCqC28mkzMlEziv9qulkqcsNn88exFIrIBFpVoujvMyvzuJy4JnfHpOTPd-H/pub?gid=1962198900&single=true&output=tsv

PSYCHE = isl.open_google_spreadsheet("PSYCHE","https://docs.google.com/spreadsheets/d/e/2PACX-1vT8AnakXtq3aTsVu48SRCqC28mkzMlEziv9qulkqcsNn88exFIrIBFpVoujvMyvzuJy4JnfHpOTPd-H/pub?gid=1962198900&single=true&output=tsv",0)
PSYCHE = isl.general_cleanup_for_table(PSYCHE)
PSYCHE = isl.cleanup_headers_specific_units(PSYCHE)

isl.export_expanded_tsv(PSYCHE, "PSYCHE_collected")
