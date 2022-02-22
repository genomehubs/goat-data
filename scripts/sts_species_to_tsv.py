#!/usr/bin/env python3

import sys
import csv
import json

fieldnames = ["family_representative","taxon_id","sequencing_status","taxon_group","submitted_gals","genome_notes","species_id","taxon_uri","project_code","common_name","lab_work_status","material_status","genus","marked_done","desc","order_group","prefix","scientific_name","family","sample_count"]

input_file = sys.stdin

data = json.load(input_file)

d = [[species[f] for f in fieldnames] for species in data]

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)
writer.writerows(d)
