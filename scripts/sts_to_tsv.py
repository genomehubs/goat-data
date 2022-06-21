#!/usr/bin/env python3

import sys
import csv
import json
import requests

url = 'https://sts.tol.sanger.ac.uk/api/v1/species'
headers = {"Authorization": "c67423e8d51d96194a1sab0e7ad9ebd5", "Project": "ALL"}

r = requests.get(url, headers=headers).json()
species_total = (r['data']['total'])

page_size = 200

sts_json = []

fieldnames = ["family_representative","taxon_id","sequencing_status","taxon_group","submitted_gals","genome_notes","species_id","taxon_uri","project_code","common_name","lab_work_status","material_status","genus","marked_done","desc","order_group","prefix","scientific_name","family","sample_count"]

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)

for page in range(1,int(species_total / page_size) + 2):
  url = f"https://sts.tol.sanger.ac.uk/api/v1/species?page={page}&page_size={page_size}"
  r   = requests.get(url, headers=headers).json()
  dl  = r['data']['list']
  d = [[species.get(f) for f in fieldnames] for species in dl]
  writer.writerows(d)

