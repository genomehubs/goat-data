#!/usr/bin/env python3

import sys
import csv
import json

fieldnames = ["institutionCode","otherCatalogNumbers","preservative","phylum","class","order","family","genus","specificEpithet","year"]

input_file = sys.stdin

data = json.load(input_file)

d = [[species.get(f) for f in fieldnames] for species in data]

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)
writer.writerows(d)
