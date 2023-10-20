# import requests
import csv


def get_from_source(
    url_opener, count_handler, row_handler, fieldnames, output_filename, token=None
):
    r = url_opener(token=token)
    r_text = r.text
    result_count = count_handler(r_text)
    print(f"count is {result_count}")
    rows = row_handler(
        r_text=r_text, result_count=result_count, fieldnames=fieldnames, token=token
    )

    with open(output_filename, "w") as output_file:
        writer = csv.writer(output_file, delimiter="\t", lineterminator="\n")
        writer.writerow(fieldnames)
        writer.writerows(rows)
