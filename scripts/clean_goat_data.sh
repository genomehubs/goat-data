#!/bin/bash
# This scipt is used to clean up old goat data directories
# The data directories are named as production-YYYY-MM-DD
# The data directories older than 7 days will be deleted
# The data directories in the list of goat_archived_list.txt will be kept
# The script will be run in dry run mode by default, use -r to run in real mode

set -eu
set -o pipefail

usage() {
    echo "Usage: $0 [-r] [-d <goat_data_dir>]" >&2
    exit 1
}

DATA_AGE_LIMIT=7
GOAT_ARCHIVED_LIST_FILE="goat_archived_list.txt"

goat_data_dir=
dry_run=true
goat_archived_list=()

while getopts ':rd:' opt; do
    case "$opt" in
        r)
            dry_run=false
            ;;
        d)
            goat_data_dir="$OPTARG"
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            usage
            ;;
        ?)
            echo "Invalid option: $OPTARG" >&2
            usage
            ;;
    esac
done

if [ -z "$goat_data_dir" ]; then
    echo "Please specify the goat data directory with -d" >&2
    usage
fi

if [ ! -d "$goat_data_dir" ]; then
    echo "Directory $goat_data_dir does not exist" >&2
    usage
fi

# IFS=$'\n' read -d '' -r -a goat_archived_list2 <<< "$(wget -qO- https://raw.githubusercontent.com/sanger-tol/readmapping/main/assets/samplesheet.csv )" || true

IFS=$'\n' read -d '' -r -a goat_archived_list < $GOAT_ARCHIVED_LIST_FILE || true

if [ ${#goat_archived_list[@]} -eq 0 ]; then
    echo "No date of data to keep found in $GOAT_ARCHIVED_LIST_FILE" >&2
    exit 1
else
    echo "Dates of data to keep:"
    printf '%s\n' "${goat_archived_list[@]}"
fi

if "$dry_run"; then
    cmd='echo'
    echo "Dry run mode!!!"
else
    cmd=''
    echo "Real run mode!!!"
fi

cd ${goat_data_dir}
count=0
count_deleted=0

for day_data_dir in production-202*.*.*; do
    count=$((count+1))
    echo "================"
    echo "Checking data directory ${day_data_dir}: $count"
    day=${day_data_dir#"production-"}
    
    if [[ " ${goat_archived_list[@]} " =~ " ${day} " ]]; then
        echo "Data $day_data_dir is in the list of data to keep, skip!"
        continue
    fi
    
    day=${day//./-}
    data_age=$((($(date +%s) - $(date +%s -d "$day")) / 86400))
    
    if [[ "$data_age" -le "$DATA_AGE_LIMIT" ]]; then
        echo "Data $day_data_dir only $data_age days old, skip!"
        continue
    else
        echo "Data $day_data_dir is $data_age days old, it will be deleted now!"
        $cmd rm -rf $day_data_dir
        count_deleted=$((count_deleted+1))
    fi
done

echo
echo "================"
echo "Checking done, in total ${count}!"
echo "Deleted $count_deleted data directories!"
echo "================"
