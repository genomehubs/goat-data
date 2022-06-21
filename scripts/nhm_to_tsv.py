#!/usr/bin/env python3

import sys
import csv
import json
import requests

url = 'https://data.nhm.ac.uk/api/action/datastore_search?filters=%7B%22project%22%3A+%5B%22darwin+tree+of+life%22%5D%7D&resource_id=05ff2255-c38a-40c9-b657-4ccb55ab2feb'

r = requests.get(url).json()
nhm_total = (r['result']['total'])

page_size = 200

nhm_json = []

fieldnames = ["institutionCode","otherCatalogNumbers","preservative","phylum","class","order","family","genus","specificEpithet","year"]

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)

# for page in range(1,int(species_total / page_size) + 2):
for page in range(0, nhm_total, page_size):
  url = f"https://data.nhm.ac.uk/api/action/datastore_search?filters=%7B%22project%22%3A+%5B%22darwin+tree+of+life%22%5D%7D&resource_id=05ff2255-c38a-40c9-b657-4ccb55ab2feb&offset={page}&limit={page_size}"
  r   = requests.get(url).json()
  dl  = r['result']['records']
  d = [[species.get(f) for f in fieldnames] for species in dl]
  writer.writerows(d)

