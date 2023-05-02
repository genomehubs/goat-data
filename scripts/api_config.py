import json
import yaml
import requests


# FOR VGL

vgl_url = 'https://raw.githubusercontent.com/vgl-hub/genome-portal/master/_data/table_tracker.yml'
vgl_fieldnames = ['common_name', 'family', 'order', 'scientific_name', 'status', 'taxon_id', 'vgp_phase']
vgl_output_filename = './sources/status_lists/vgl.tsv'

def vgl_hub_count_handler(r_text):
    vgp_yaml = yaml.safe_load(r_text)
    return len(vgp_yaml['toc'])

def vgl_row_handler(r_text,_, fieldnames):
    
    vgp_yaml = yaml.safe_load(r_text)
    result = []
    for species in vgp_yaml['toc']:
        d = [species.get(f) for f in fieldnames]
        result.append(d)
    return result
  
  
# FOR NHM

nhm_url = 'https://data.nhm.ac.uk/api/action/datastore_search?filters=%7B%22project%22%3A+%5B%22darwin+tree+of+life%22%5D%7D&resource_id=05ff2255-c38a-40c9-b657-4ccb55ab2feb'
nhm_fieldnames = ["institutionCode","otherCatalogNumbers","preservative","phylum","class","order","family","genus","specificEpithet","year"]
nhm_output_filename = './sources/status_lists/nhm.tsv'

def nhm_api_count_handler(r_text):
    j = json.loads(r_text)
    nhm_total = j['result']['total']
    return nhm_total

def nhm_row_handler(_, result_count, fieldnames):
    page_size = 200
    result = []
    for page in range(0, result_count, page_size):
        # does this need to be somewhere else??
        url = f"https://data.nhm.ac.uk/api/action/datastore_search?filters=%7B%22project%22%3A+%5B%22darwin+tree+of+life%22%5D%7D&resource_id=05ff2255-c38a-40c9-b657-4ccb55ab2feb&offset={page}&limit={page_size}"
        r   = requests.get(url).json()
        dl  = r['result']['records']
        d = [[species.get(f) for f in fieldnames] for species in dl]
        result.extend(d)
    return result