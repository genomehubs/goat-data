#!/usr/bin/env python

import csv
import sys
import requests

output_filename = f"{sys.argv[1]}/jgi_1kfg.tsv"

try:
    url = "https://gold-ws.jgi.doe.gov"
    OFFLINE_TOKEN = sys.argv[2]
    ACCESS_TOKEN = requests.get(
        url + "/exchange?offlineToken=" + OFFLINE_TOKEN
    ).content.decode()

    headers = {"Authorization": "Bearer " + ACCESS_TOKEN, "Accept": "application/json"}

    r = requests.get(
        url + "/api/v1/organisms?studyGoldId=Gs0000001", headers=headers
    ).json()
    org2taxid = {}

    for organism in r:
        org2taxid[organism["organismGoldId"]] = organism["ncbiTaxId"]

    r = requests.get(
        url + "/api/v1/projects?studyGoldId=Gs0000001", headers=headers
    ).json()

    fieldnames = [
        "projectGoldId",
        "projectName",
        "legacyGoldId",
        "studyGoldId",
        "biosampleGoldId",
        "organismGoldId",
        "itsProposalId",
        "itsSpid",
        "itsSampleId",
        "pmoProjectId",
        "gptsProposalId",
        "ncbiBioProjectAccession",
        "ncbiBioSampleAccession",
        "projectStatus",
        "sequencingStatus",
        "jgiFundingProgram",
        "jgiFundingYear",
        "hmpId",
        "modDate",
        "addDate",
        "sequencingStrategy",
        "sequencingCenters",
        "seqMethod",
        "genomePublications",
        "otherPublications",
        "sraExperimentIds",
    ]

    with open(output_filename, "w") as output_file:
        writer = csv.writer(output_file, delimiter="\t", lineterminator="\n")
        writer.writerow(fieldnames + ["ncbiTaxId"])

        for project in r:
            d = [project.get(f) for f in fieldnames]
            if project["sequencingStrategy"] == "Whole Genome Sequencing":
                writer.writerow(d + [org2taxid[project["organismGoldId"]]])

except Exception:
    print(f"something has gone wrong: {output_filename}")
    try:
        open(f"{output_filename}.failed", "x")
    except FileExistsError:
        sys.exit(1)
