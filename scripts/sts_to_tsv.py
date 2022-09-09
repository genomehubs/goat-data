#!/usr/bin/env python3

import sys
import csv
import json
import requests

url = 'https://sts.tol.sanger.ac.uk/api/v1/species'
headers = {"Authorization": sys.argv[1], "Project": "ALL"}

r = requests.get(url, headers=headers).json()
species_total = (r['data']['total'])

page_size = 200

sts_json = []

fieldnames = ['available_samples_ready', 'common_name', 'desc', 'family', 'family_representative', 'family_representative_link', 'genome_notes', 'genus', 'infra_epithet', 'lab_work_status', 'marked_done', 'material_status', 'order_group', 'prefix', 'project_code', 'sample_count', 'scientific_name', 'sequencing_material_status_updated_at', 'sequencing_status', 'species_id', 'submitted_gals', 'taxon_group', 'taxon_id', 'taxon_uri', 'tissue_depleted', 'tissue_status']
fieldnames.extend(['sequencing_status_simple', 'sequencing_status_dtol', 'sequencing_status_asg', 'sequencing_status_ergapi', 'sequencing_status_vgp', 'sequencing_status_blax', 'sequencing_status_durb', 'sequencing_status_rnd', 'sequencing_status_lawn', 'sequencing_status_berri', 'sequencing_status_meier', 'sequencing_status_misk', 'sample_collected', 'sample_acquired', 'in_progress'])
output_file = sys.stdout
writer = csv.writer(output_file, delimiter='\t', lineterminator='\n')
writer.writerow(fieldnames)

for page in range(1,int(species_total / page_size) + 2):
  url = f"https://sts.tol.sanger.ac.uk/api/v1/species?page={page}&page_size={page_size}"
  r   = requests.get(url, headers=headers).json()
  dl  = r['data']['list']

  for species in dl:

    sequencing_status_simple = 'sample_collected' # default
    lws = species.get('lab_work_status')
    if 'NOVEL' in str(lws):
      sequencing_status_simple = 'sample_acquired'
    elif 'ASSIGNED_TO_LAB' in str(lws):
      sequencing_status_simple = 'sample_acquired'
    else:
      sequencing_status_simple = 'in_progress'

    species['sequencing_status_simple'] = sequencing_status_simple

    pc = species.get('project_code')
    for p in pc:
      species['sequencing_status_' + p.lower()] = sequencing_status_simple

    if sequencing_status_simple == 'sample_collected':
      species['sample_collected'] = ','.join(pc)
    if sequencing_status_simple == 'sample_acquired':
      species['sample_collected'] = ','.join(pc)
      species['sample_acquired']  = ','.join(pc)
    if sequencing_status_simple == 'in_progress':
      species['sample_collected'] = ','.join(pc)
      species['sample_acquired']  = ','.join(pc)
      species['in_progress']      = ','.join(pc)

    species['submitted_gals']     = ','.join(species.get('submitted_gals'))

    d = [species.get(f) for f in fieldnames]
    writer.writerow(d)
