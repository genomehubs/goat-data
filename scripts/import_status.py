import import_status_lib as isl
import sys

# from imp import reload
# reload(isl)

private_tsv = isl.open_private_tsv(sys.argv[1])
private_tsv = private_tsv.reset_index()  # make sure indexes pair with number of rows

for index, row in private_tsv.iterrows():
    print(row["project_acronym"]
        #   , str(row["published_url"])
          , int(row["start_header_line"]))
    try:
        isl.processing_schema_2_5_lists(row["project_acronym"]
                                       , str(row["published_url"])
                                       , int(row["start_header_line"]))
    except:
        print('something has gone wrong: ', row["project_acronym"])
