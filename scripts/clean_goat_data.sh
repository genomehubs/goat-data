#!/bin/bash

# This script is used to clean up old goat data directories
# The data directories are named as production-YYYY-MM-DD
# The script will keep the data directories that are in the list of goat_archived_list.txt
# The script will keep the data directories that are within the days to keep
# The script will keep the data directories that are the first data of the month if keep_first_data_of_month is enabled
# The script will delete the data directories that are not in the list of data to keep 
# The script will delete the ES index for the data directories that are deleted if remove_prod_es_index is enabled

set -e
set -o pipefail

usage() {
    echo "Usage: $0 [-r] [-m] [-d <goat_data_dir>] [-k <days_to_keep>] [-p] " >&2
    exit 1
}

GOAT_ARCHIVED_LIST_FILE="goat_archived_list.txt"
GOAT_PROD_VM="tol-goat-prod-run1"
goat_data_dir=''
days_to_keep=3
keep_first_data_of_month=false
dry_run=true
remove_prod_es_index=false
goat_archived_list=()

while getopts ':rmd:k:p' opt; do
    case "$opt" in
        r)
            dry_run=false
            ;;
        m)
            keep_first_data_of_month=true
            ;;
        d)
            goat_data_dir="$OPTARG"
            ;;
        k)
            days_to_keep="$OPTARG"
            ;;
        p)
            remove_prod_es_index=true
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

IFS=$'\n' read -d '' -r -a goat_archived_list <<< "$(wget -qO- https://raw.githubusercontent.com/genomehubs/goat-data/main/scripts/goat_archived_list.txt )" || true

# IFS=$'\n' read -d '' -r -a goat_archived_list < $GOAT_ARCHIVED_LIST_FILE || true

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
data_dir_to_keep=()
current_month=""
previous_month=""
day_data_dir=""
previous_day_data_dir=""

for day_data_dir in `ls -d production-202[0-9].[0-1][0-9].[0-3][0-9] | sort -r`; do
    count=$((count+1))
    echo "================"
    echo "Checking data directory ${day_data_dir}: $count"
    day=${day_data_dir#"production-"}
    current_month=${day:0:7}

    # keep the data directory if it is in the list of data to keep
    if [[ " ${goat_archived_list[@]} " =~ " ${day} " ]]; then
        echo "Data $day_data_dir is in the list of data to keep, keep!"
        if [[ ! " ${data_dir_to_keep[@]} " =~ " ${day_data_dir} " ]]; then
            data_dir_to_keep+=($day_data_dir)
        fi
    fi

    # keep the data directory if it is within the days to keep
    if [[ "$count" -le "$days_to_keep" ]]; then
        echo "Data ${day_data_dir} is within the days to keep, keep!"
        if [[ ! " ${data_dir_to_keep[@]} " =~ " ${day_data_dir} " ]]; then
            data_dir_to_keep+=($day_data_dir)
        fi
    fi

    if ! $keep_first_data_of_month; then
        echo "Keep first data of the month is disabled!"
        continue
    fi

    # Keep the data directory if it is the first data of the month
    if [[ "$current_month" != "$previous_month" ]]; then
        echo "Previous day data directory is the first data of previous month, keep!"
        if [[ "$previous_month" != "" ]] && [[ ! " ${data_dir_to_keep[@]} " =~ " ${previous_day_data_dir} " ]]; then
            data_dir_to_keep+=($previous_day_data_dir)
        fi
    fi

    previous_month=$current_month    
    previous_day_data_dir=$day_data_dir
done

if $keep_first_data_of_month; then
    echo "The last day data directory is the first data of the last month, keep!"
    if [[ ! " ${data_dir_to_keep[@]} " =~ " ${day_data_dir} " ]]; then
        data_dir_to_keep+=($day_data_dir)
    fi
fi

echo
echo "================"
echo "Checking done, in total ${count}!"
echo "The number of data dir to keep: ${#data_dir_to_keep[@]}"
printf '%s\n' ${data_dir_to_keep[@]}
echo "================"

count_deleted=0
for day_data_dir in `ls -d production-202[0-9].[0-1][0-9].[0-3][0-9]`; do
    if [[ ! " ${data_dir_to_keep[@]} " =~ " ${day_data_dir} " ]]; then
        echo "================"
        echo "Delete data directory ${day_data_dir}"
        $cmd rm -rf $day_data_dir
        count_deleted=$((count_deleted+1))

        # Remove snapshots data from s3
        "$cmd" s3cmd del --recursive "s3://goat/snapshots/${day_data_dir}/"

        # Remove release data from s3
        "$cmd" s3cmd del --recursive "s3://goat/releases/${day_data_dir}/"

        if $remove_prod_es_index; then
            echo "Delete ES index for ${day_data_dir}"
            day=${day_data_dir#"production-"}
            $cmd ssh $GOAT_PROD_VM "curl -X DELETE es1:9200/*-${day}"
        fi
    fi
done

echo "================"
echo "In total ${count_deleted} data directories are deleted!"
echo "================"
