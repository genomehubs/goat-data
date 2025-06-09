#!/bin/bash

set -e
set -o pipefail

usage() {
    echo "Usage: $0 [-r] [-m] [-d <goat_data_dir>] [-k <days_to_keep>] " >&2
    exit 1
}

GOAT_ARCHIVED_LIST_FILE="goat_archived_list.txt"
goat_data_dir='s3://goat/snapshots/'
days_to_keep=3
keep_first_data_of_month=false
dry_run=true

goat_archived_list=()

while getopts ':rmd:k:h' opt; do
    case "$opt" in
        h)
            usage
            ;;
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

if s3cmd ls "$goat_data_dir" >/dev/null 2>&1; then
    echo "Bucket $goat_data_dir exists."
else
    echo "Bucket $goat_data_dir does not exist or access denied"
    usage
fi

IFS=$'\n' read -d '' -r -a goat_archived_list <<< "$(wget -qO- https://raw.githubusercontent.com/genomehubs/goat-data/main/scripts/goat_archived_list.txt )" || true

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

count=0
data_dir_to_keep=()
current_month=""
previous_month=""
day_data_dir=""
previous_day_data_dir=""

# Capture s3cmd output into an array
echo "Fetching S3 directory list..."
mapfile -t s3_lines < <(s3cmd ls "$goat_data_dir" | sort -r)

echo "Found ${#s3_lines[@]} directories to process"
printf '%s\n' "${s3_lines[@]}"

for line in "${s3_lines[@]}"; do
    count=$((count+1))
    echo "----------------"
    echo "Checking data bucket ${line}: $count"

    day_data_dir=$(echo "$line" | awk '{print $NF}')
    day_data_dir=$(basename "$day_data_dir")

    # Extract day from directory name (assuming format: production-YYYY-MM-DD)
    day=${day_data_dir#"production-"}
    current_month=${day:0:7}

    echo "Processing: $day_data_dir (day: $day, month: $current_month)"

    # Keep the data directory if it is in the list of data to keep
    if [[ " ${goat_archived_list[*]} " =~ " ${day} " ]]; then
        echo "Data $day_data_dir is in the list of data to keep, keep!"
        if [[ ! " ${data_dir_to_keep[*]} " =~ " ${day_data_dir} " ]]; then
            data_dir_to_keep+=("$day_data_dir")
        fi
    fi

    # Keep the data directory if it is within the days to keep
    if [[ "$count" -le "$days_to_keep" ]]; then
        echo "Data ${day_data_dir} is within the days to keep, keep!"
        if [[ ! " ${data_dir_to_keep[*]} " =~ " ${day_data_dir} " ]]; then
            data_dir_to_keep+=("$day_data_dir")
        fi
    fi

    # Skip month-first logic if disabled
    if [[ "$keep_first_data_of_month" != "true" ]]; then
        echo "Keep first data of the month is disabled!"
        previous_month=$current_month    
        previous_day_data_dir=$day_data_dir
        continue
    fi

    # Keep the data directory if it is the first data of the month
    if [[ "$current_month" != "$previous_month" && -n "$previous_month" ]]; then
        echo "Previous day data directory ($previous_day_data_dir) is the first data of previous month, keep!"
        if [[ ! " ${data_dir_to_keep[*]} " =~ " ${previous_day_data_dir} " ]]; then
            data_dir_to_keep+=("$previous_day_data_dir")
        fi
    fi

    previous_month=$current_month    
    previous_day_data_dir=$day_data_dir
done

# Handle the last entry for month-first logic
if [[ "$keep_first_data_of_month" == "true" && -n "$previous_day_data_dir" ]]; then
    if [[ ! " ${data_dir_to_keep[*]} " =~ " ${previous_day_data_dir} " ]]; then
        echo "Adding last entry as first of its month: $previous_day_data_dir"
        data_dir_to_keep+=("$previous_day_data_dir")
    fi
fi

echo "================"
echo "Final directories to keep:"
printf '%s\n' "${data_dir_to_keep[@]}"

# Deletion phase
echo "================"
echo "Starting deletion phase..."
echo "In total ${count} directories found, ${#data_dir_to_keep[@]} directories to keep."

# Process the same array for deletion
count_deleted=0
for line in "${s3_lines[@]}"; do
    echo "----------------"
    echo "Checking data bucket for deletion: $line"
    day_data_dir=$(echo "$line" | awk '{print $NF}')
    day_data_dir=$(basename "$day_data_dir")
    echo "Processing for deletion: $day_data_dir"

    match_found=false
    for dir in "${data_dir_to_keep[@]}"; do
        if [[ "$dir" == "$day_data_dir" ]]; then
            match_found=true
            break
        fi
    done
    if [[ "$match_found" == false ]]; then
       echo "Delete data directory ${day_data_dir}"
       count_deleted=$((count_deleted+1))

       # Remove snapshots data from s3
       echo "Removing snapshots data from s3: ${day_data_dir}"
       $cmd s3cmd del --recursive "s3://goat/snapshots/${day_data_dir}/"

        # Remove release data from s3
        echo "Removing release data from s3: ${day_data_dir}"
        day_release=$(echo "$day_data_dir" | sed 's/production-//')
        $cmd s3cmd del --recursive "s3://goat/releases/${day_release}/"
    fi
done

echo "================"
echo "In total ${count_deleted} data directories are deleted!"
echo "================"
