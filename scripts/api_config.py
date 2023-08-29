import json
import yaml
import requests

#####################################################################
# VGL
#####################################################################

vgl_fieldnames = [
    "common_name",
    "family",
    "order",
    "scientific_name",
    "status",
    "taxon_id",
    "vgp_phase",
]
vgl_output_filename = "./sources/status_lists/vgp.tsv"


def vgl_url_opener(**kwargs):
    vgl_url = "https://raw.githubusercontent.com/vgl-hub/genome-portal/master/_data/table_tracker.yml"
    return requests.get(vgl_url, stream=True)


def vgl_hub_count_handler(r_text):
    vgp_yaml = yaml.safe_load(r_text)
    return len(vgp_yaml["toc"])


def vgl_row_handler(r_text, fieldnames, **kwargs):
    vgp_yaml = yaml.safe_load(r_text)
    result = []
    for species in vgp_yaml["toc"]:
        d = [species.get(f) for f in fieldnames]
        result.append(d)
    return result


#####################################################################
# NHM
#####################################################################

nhm_fieldnames = [
    "institutionCode",
    "otherCatalogNumbers",
    "preservative",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "specificEpithet",
    "year",
]
nhm_output_filename = "./sources/status_lists/nhm.tsv"
nhm_post_data = {
    "size": "1000",
    "resource_ids": ["05ff2255-c38a-40c9-b657-4ccb55ab2feb"],
    "query": {
        "filters": {
            "and": [
                {
                    "string_equals": {
                        "fields": ["project"],
                        "value": "darwin tree of life",
                    },
                },
            ],
        },
    },
}


nhm_url = "https://data.nhm.ac.uk/api/3/action/datastore_multisearch"
nhm_headers = {"content-type": "application/json"}


def nhm_url_opener(**kwargs):
    return requests.post(nhm_url, headers=nhm_headers, json=nhm_post_data)


def nhm_api_count_handler(r_text):
    j = json.loads(r_text)
    nhm_total = j["result"]["total"]
    return nhm_total


def nhm_row_handler(fieldnames, **kwargs):
    nhm_post_data_after = nhm_post_data
    result = []

    while True:
        response = requests.post(nhm_url, headers=nhm_headers, json=nhm_post_data_after)
        r = response.json()
        dl = r["result"]["records"]
        d = [[species["data"].get(f) for f in fieldnames] for species in dl]
        # split catalogue headers at this point
        result.extend(d)
        print(r["result"]["after"])
        nhm_post_data_after.update({"after": r["result"]["after"]})
        if r["result"]["after"] == None:
            break

    return result


#####################################################################
# STS
#####################################################################

sts_url = "https://sts.tol.sanger.ac.uk/api/v1/species"
sts_output_filename = "./sources/status_lists/sts.tsv"
sts_fieldnames = [
    "available_samples_ready",
    "common_name",
    "desc",
    "family",
    "family_representative",
    "family_representative_link",
    "genome_notes",
    "genus",
    "infra_epithet",
    "lab_work_status",
    "marked_done",
    "material_status",
    "order_group",
    "prefix",
    "project_code",
    "sample_count",
    "scientific_name",
    "sequencing_material_status_updated_at",
    "sequencing_status",
    "species_id",
    "submitted_gals",
    "taxon_group",
    "taxon_id",
    "taxon_uri",
    "tissue_depleted",
    "tissue_status",
    "sequencing_status_simple",
    "sequencing_status_dtol",
    "sequencing_status_asg",
    "sequencing_status_ergapi",
    "sequencing_status_vgp",
    "sequencing_status_blax",
    "sequencing_status_durb",
    "sequencing_status_rnd",
    "sequencing_status_lawn",
    "sequencing_status_berri",
    "sequencing_status_meier",
    "sequencing_status_misk",
    "sample_collected",
    "sample_acquired",
    "in_progress",
]


def sts_url_opener(token):
    return requests.get(sts_url, headers={"Authorization": token, "Project": "ALL"})


def sts_api_count_handler(r_text):
    j = json.loads(r_text)
    return j["data"]["total"]


def sts_row_handler(result_count, fieldnames, token, **kwargs):
    page_size = 200
    result = []

    for page in range(1, int(result_count / page_size) + 2):
        print(page)

        url = f"{sts_url}?page={page}&page_size={page_size}"
        r = requests.get(url, headers={"Authorization": token, "Project": "ALL"}).json()
        dl = r["data"]["list"]

        for species in dl:
            sequencing_status_simple = "sample_collected"  # default
            lws = species.get("lab_work_status")
            if "NOVEL" in str(lws) or "ASSIGNED_TO_LAB" in str(lws):
                sequencing_status_simple = "sample_acquired"
            else:
                sequencing_status_simple = "in_progress"

            species["sequencing_status_simple"] = sequencing_status_simple

            pc = species.get("project_code")
            for p in pc:
                species[f"sequencing_status_{p.lower()}"] = sequencing_status_simple

            if sequencing_status_simple == "in_progress":
                species["sample_collected"] = ",".join(pc)
                species["sample_acquired"] = ",".join(pc)
                species["in_progress"] = ",".join(pc)

            elif sequencing_status_simple == "sample_acquired":
                species["sample_collected"] = ",".join(pc)
                species["sample_acquired"] = ",".join(pc)
            elif sequencing_status_simple == "sample_collected":
                species["sample_collected"] = ",".join(pc)
            species["submitted_gals"] = ",".join(species.get("submitted_gals"))

            d = [[species.get(f) for f in fieldnames]]
            result.extend(d)

    return result
