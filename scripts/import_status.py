import traceback
import import_status_lib as isl
import sys

# from imp import reload
# reload(isl)

projects = [
    "ATLASEA",
    "BEENOME100",
    "BGE",
    "CBP",
    "EBPN",
    "EUROFISH",
    "ERGA-CH",
    "LOEWE-TBG",
    "OTHER",
    "SPAIN-HSP",
    "SOLVENIA-HSP",
    "GREECE-HSP",
    "YGG",
]

try:
    private_tsv = isl.open_private_tsv(sys.argv[2])
    private_tsv = (
        private_tsv.reset_index()
    )  # make sure indexes pair with number of rows

    for index, row in private_tsv.iterrows():
        print(
            row["project_acronym"],
            int(row["start_header_line"]),
        )
        try:
            isl.processing_schema_2_5_lists(
                row["project_acronym"],
                str(row["published_url"]),
                int(row["start_header_line"]),
                sys.argv[1],
            )
        except Exception:
            print("something has gone wrong: ", row["project_acronym"])
            print(traceback.format_exc())
            try:
                open(f"{sys.argv[1]}/{row['project_acronym']}_expanded.tsv.failed", "x")
            except FileExistsError:
                sys.exit(1)
except Exception:
    for project in projects:
        try:
            open(f"{sys.argv[1]}/{project}_expanded.tsv.failed", "x")
            pass
        except FileExistsError:
            sys.exit(1)
