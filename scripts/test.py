#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

# Create the parser
parser = argparse.ArgumentParser(description="Process some integers.")

# Add the arguments
parser.add_argument("RELEASE", type=str, help="The release version")
parser.add_argument("DIRECTORY", type=str, help="The directory")
parser.add_argument("RESOURCES", type=str, help="The resources directory")

# Parse the arguments
args = parser.parse_args()

# Set the variables
RELEASE = args.RELEASE
DIRECTORY = args.DIRECTORY
RESOURCES = args.RESOURCES


# Define fail function
def fail(message, code=1):
    print(message, file=sys.stderr)
    os.chdir(workdir)
    shutil.rmtree(tmpdir)
    subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "DELETE",
            f"es1:9200/_snapshot/current/{RELEASE}_pre{DIRECTORY}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sys.exit(code)


# Get working directory and create temporary directory
workdir = os.getcwd()
tmpdir = tempfile.mkdtemp()

# Create empty file in temporary directory
with open(os.path.join(tmpdir, "from_resources.txt"), "w") as f:
    pass

# List YAML files available in sources and on S3
SUFFIX = ".yaml"
SOURCEYAMLS = (
    subprocess.run(
        [
            "ls",
            f"sources/{DIRECTORY}/*types{SUFFIX}",
            f"sources/{DIRECTORY}/*names{SUFFIX}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    .stdout.decode()
    .splitlines()
)
S3YAMLS = (
    subprocess.run(
        ["s3cmd", "ls", f"s3://goat/resources/{DIRECTORY}", "--recursive"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    .stdout.decode()
    .splitlines()
)
S3YAMLS = [line for line in S3YAMLS if SUFFIX in line]
S3YAMLS = [line.split()[-1] for line in S3YAMLS]

if SOURCEYAMLS:
    S3YAMLS = [
        yaml
        for yaml in S3YAMLS
        if os.path.basename(yaml)
        not in [os.path.basename(source) for source in SOURCEYAMLS]
    ]

# Assuming SOURCEYAMLS and S3YAMLS are lists
for YAML in SOURCEYAMLS + S3YAMLS:
    if not YAML:
        continue
    YAMLFILE = os.path.basename(YAML)
    print(YAMLFILE)
    if RESOURCES:
        # Fetch YAML
        result = subprocess.run(
            [
                "s3cmd",
                "get",
                f"s3://goat/resources/{DIRECTORY}/{YAMLFILE}",
                f"{tmpdir}/{YAMLFILE}",
            ],
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            print("YAML from resources")
            with open(f"{tmpdir}/from_resources.txt", "a") as f:
                f.write(YAMLFILE + "\n")
        else:
            print("YAML from sources")
            shutil.copy(YAML, f"{tmpdir}/{YAMLFILE}")
        with open(f"{tmpdir}/{YAMLFILE}", "r") as f:
            data = yaml.safe_load(f)
        FILE = data.get("file", {}).get("name")
        if not FILE:
            print("No file specified in YAML")
            continue
        # Fetch data file
        if os.path.exists(f"{RESOURCES}/{DIRECTORY}/{FILE}"):
            shutil.copy(f"{RESOURCES}/{DIRECTORY}/{FILE}", f"{tmpdir}/{FILE}")
            print("DATA file from local resources")
            with open(f"{tmpdir}/from_resources.txt", "a") as f:
                f.write(FILE + "\n")
        else:
            subprocess.run(
                [
                    "s3cmd",
                    "get",
                    f"s3://goat/resources/{DIRECTORY}/{FILE}",
                    f"{tmpdir}/{FILE}",
                ]
            )
            if result.returncode == 0:
                print("DATA file from s3 resources")
                with open(f"{tmpdir}/from_resources.txt", "a") as f:
                    f.write(FILE + "\n")
            else:
                print("DATA file from sources")
                subprocess.run(
                    [
                        "s3cmd",
                        "get",
                        f"s3://goat/sources/{DIRECTORY}/{FILE}",
                        f"{tmpdir}/{FILE}",
                    ]
                )
    else:
        # Fetch YAML
        shutil.copy(YAML, f"{tmpdir}/{YAMLFILE}")
        with open(f"{tmpdir}/{YAMLFILE}", "r") as f:
            data = yaml.safe_load(f)
        FILE = data.get("file", {}).get("name")
        if not FILE:
            continue
        # Fetch data file
        subprocess.run(
            [
                "s3cmd",
                "get",
                f"s3://goat/sources/{DIRECTORY}/{FILE}",
                f"{tmpdir}/{FILE}",
            ],
            stderr=subprocess.DEVNULL,
        )
    if not os.path.exists(f"{tmpdir}/{FILE}"):
        fail(f"unable to find data file {FILE} required by {YAML}")
    # check if file has been updated since last release
    result = subprocess.run(
        ["s3cmd", "info", f"s3://goat/sources/{DIRECTORY}/{FILE}"],
        stdout=subprocess.PIPE,
    )
    s3_md5 = [
        line for line in result.stdout.decode().splitlines() if "MD5 sum" in line
    ][0].split()[-1]
    result = subprocess.run(["md5sum", f"{tmpdir}/{FILE}"], stdout=subprocess.PIPE)
    local_md5 = result.stdout.decode().split()[0]
    if s3_md5 != local_md5:
        # update associated YAML file with release date
        with open(f"{tmpdir}/{YAMLFILE}", "r") as f:
            data = yaml.safe_load(f)
        data["file"]["source_date"] = RELEASE.replace(".", "-")
        with open(f"{tmpdir}/{YAMLFILE}.tmp", "w") as f:
            yaml.dump(data, f)
        os.rename(f"{tmpdir}/{YAMLFILE}.tmp", f"{tmpdir}/{YAMLFILE}")
