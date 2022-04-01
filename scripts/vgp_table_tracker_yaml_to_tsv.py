#!/usr/bin/env python3

import sys
import csv
import yaml

fieldnames = ['common_name', 'family', 'order', 'scientific_name', 'status', 'taxon_id', 'vgp_phase']

input_file = sys.stdin

data = yaml.safe_load(input_file)

d = [[asm[f] for f in fieldnames] for asm in data['toc']]

output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', dialect="unix")
writer.writerow(fieldnames)
writer.writerows(d)
