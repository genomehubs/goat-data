#!/usr/bin/env python3

import sys
import csv
import yaml
import requests

url = 'https://raw.githubusercontent.com/vgl-hub/genome-portal/master/_data/table_tracker.yml'

r = requests.get(url, stream=True)
if r.status_code == 404:
  raise requests.RequestException("404 Not Found!")
r.raw.decode_content = True
vgp_yaml = yaml.safe_load(r.raw)

fieldnames = ['common_name', 'family', 'order', 'scientific_name', 'status', 'taxon_id', 'vgp_phase']

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)

for species in vgp_yaml['toc']:
  d = [species.get(f) for f in fieldnames]
  writer.writerow(d)
