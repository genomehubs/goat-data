import requests
import csv

def get_from_source(url_template, count_handler, row_handler, fieldnames ,output_filename):
    r = requests.get(url_template, stream=True)
    r_text = r.text
    result_count = count_handler(r_text)
    print(f'count is {result_count}')
    rows = row_handler(r_text, result_count, fieldnames)
    
    with open(output_filename, 'w') as output_file:
        writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
        writer.writerow(fieldnames)
        writer.writerows(rows)