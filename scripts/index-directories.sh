#!/bin/bash

workdir=$(pwd)
tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')

function fail {
    printf '%s\n' "$1" >&2
    cd $workdir
    rm -rf $tmpdir
    curl -s -X DELETE "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}" &>/dev/null
    exit "${2-1}"
}

> $tmpdir/from_resources.txt

# List YAML files available in sources and on S3
SUFFIX=.yaml
SOURCEYAMLS=$(ls sources/$DIRECTORY/*types$SUFFIX sources/$DIRECTORY/*names$SUFFIX 2>/dev/null);
S3YAMLS=$(s3cmd ls s3://goat/resources/$DIRECTORY --recursive | grep $SUFFIX | awk '{print $NF}' 2>/dev/null)
if [ ! -z "$SOURCEYAMLS" ]; then
  S3YAMLS=$(grep -vFf <(echo "$SOURCEYAMLS" | awk -F"/" '{print $NF}') <(echo "$S3YAMLS") 2>/dev/null)
fi

# Loop through YAMLs fetching YAML and data from S3 if available else from sources
while read YAML; do
  if [ -z "$YAML" ]; then
    continue
  fi
  YAMLFILE=$(basename $YAML)
  if [ ! -z "$RESOURCES" ]; then
    # Fetch YAML
    s3cmd get s3://goat/resources/$DIRECTORY/$YAMLFILE $tmpdir/$YAMLFILE 2>/dev/null
    if [ $? -eq 0 ]; then
      echo $YAMLFILE >> $tmpdir/from_resources.txt
    else
      cp $YAML $tmpdir/$YAMLFILE
    fi
    FILE=$(cat $tmpdir/$YAMLFILE | yq -r '.file.name' 2>/dev/null)
    if [[ -z $FILE ]] || [[ "$FILE" == null ]]; then
      continue
    fi
    # Fetch data file
    if [ -e "$RESOURCES/$DIRECTORY/$FILE" ]; then
      cp $RESOURCES/$DIRECTORY/$FILE $tmpdir/$FILE
      echo $FILE >> $tmpdir/from_resources.txt
    else
      s3cmd get s3://goat/resources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
      if [[ $? -eq 0 ]]; then
        echo $FILE >> $tmpdir/from_resources.txt
      else
        s3cmd get s3://goat/sources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
      fi
    fi
  else
  # Fetch YAML
    cp $YAML $tmpdir/$YAMLFILE
    FILE=$(cat $tmpdir/$YAMLFILE | yq -r '.file.name' 2>/dev/null)
    if [[ -z $FILE ]] || [[ "$FILE" == null ]]; then
      continue
    fi
    # Fetch data file
    s3cmd get s3://goat/sources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
  fi
  if [ ! -e "$tmpdir/$FILE" ]; then
    fail "unable to find data file $FILE required by $YAML"
  fi
  # check if file has been updated since last release
  diff -q \
    <(s3cmd info s3://goat/sources/$DIRECTORY/$FILE || true | grep "MD5 sum" | awk '{print $NF}') \
    <(md5sum $tmpdir/$FILE | awk '{print $1}')
  if [ $? -ne 0 ]; then
    # update associated YAML file with release date
    cat $tmpdir/$YAMLFILE | yq '.file.source_date="'${RELEASE//./-}'"' > $tmpdir/$YAMLFILE.tmp && mv $tmpdir/$YAMLFILE.tmp $tmpdir/$YAMLFILE
  fi
done <<< $(printf "$SOURCEYAMLS\n$S3YAMLS\n" | sed '/^$/d')

# Fetch names directory
if [ ! -z "$RESOURCES" ]; then
  s3cmd get s3://goat/resources/$DIRECTORY/names $tmpdir --recursive 2>/dev/null
  if [ $? -eq 0 ]; then
    echo names >> $tmpdir/from_resources.txt
    # Add extra files from sources
    while read FILE; do
      if [ ! -e "$tmpdir/names/$FILE" ]; then
        cp sources/$DIRECTORY/names/$FILE $tmpdir/names/
      fi
    done <<< $(ls sources/$DIRECTORY/names 2>/dev/null)
  else
    s3cmd get s3://goat/sources/$DIRECTORY/names $tmpdir --recursive 2>/dev/null
  fi
else
  s3cmd get s3://goat/sources/$DIRECTORY/names $tmpdir --recursive 2>/dev/null
fi

# Fetch tests directories
cp -r sources/$DIRECTORY/*tests $tmpdir 2>/dev/null
if [ ! -z "$RESOURCES" ]; then
  while read TESTURL; do
    if [ -z "$TESTURL" ]; then
      continue
    fi
    TESTS=$(basename $TESTURL)
    s3cmd get s3://goat/resources/$DIRECTORY/$TESTS $tmpdir --recursive 2>/dev/null
    if [ $? -eq 0 ]; then
      echo $TESTS >> $tmpdir/from_resources.txt
      # Add extra tests from sources
      while read YAML; do
        if [ ! -e "$tmpdir/$TESTS/$YAML" ]; then
          cp sources/$DIRECTORY/$TESTS/$YAML $tmpdir/$TESTS/
        fi
      done <<< $(ls sources/$DIRECTORY/$TESTS 2>/dev/null)
    else
      cp -r sources/$DIRECTORY/$TESTS $tmpdir/$TESTS 2>/dev/null
    fi
  done <<< $(s3cmd ls s3://goat/resources/$DIRECTORY/ | awk '{print $NF}' | grep 'tests$')
fi


if [ ! -z "$RESOURCES" ]; then
  # Make a snapshot to roll back to in case indexing fails

  # Generate list of indices
  INDICES="attributes-*$RELEASE,identifiers-*$RELEASE,$TYPE-*$RELEASE"
  if [ $TYPE != feature ] && [ $TYPE != taxon ]; then
    INDICES="$INDICES,taxon-*$RELEASE"
  fi
  curl -s -X DELETE "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}" &>/dev/null
  curl -s -X PUT    "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}?wait_for_completion=true&pretty" \
    -H 'Content-Type: application/json' \
    -d' { "indices": "'$INDICES'", "include_global_state":false}'
fi

# Fetch config file
if ! yq '.common.hub.version="'$RELEASE'"' $workdir/sources/goat.yaml > $tmpdir/goat.yaml 2>/dev/null; then
  # Fallback if yq is missing or fails
  cp $workdir/sources/goat.yaml $tmpdir/goat.yaml
fi

if [ ! -s "$tmpdir/goat.yaml" ]; then
  fail "config file was not created at $tmpdir/goat.yaml"
fi

ls -al $tmpdir

# Run genomehubs index on the collated files
docker run --rm --network=host \
  --user root \
  -v $tmpdir:/genomehubs/sources \
  genomehubs/genomehubs:$DOCKERVERSION bash -c \
    "genomehubs index \
    --es-host es1:9200 \
    --taxonomy-source $TAXONOMY \
    --config-file /genomehubs/sources/goat.yaml \
    --${TYPE}-dir /genomehubs/sources $FLAGS && \
    chown -R $(id -u):$(id -g) /genomehubs/sources"

# If index was successful, move files from resources to release branch/bucket
if [ $? -eq 0 ]; then
  if [ ! -z "$RESOURCES" ]; then
    echo $RELEASE > $tmpdir/latest-release.txt
    s3cmd put setacl --acl-public $tmpdir/latest-release.txt s3://goat/resources/$DIRECTORY/
    echo Reading $(wc -l $tmpdir/from_resources.txt) files to move from $tmpdir/from_resources.txt
    while read FILE; do
      if [[ $FILE == *yaml ]]; then
        echo move $FILE to github
        mkdir -p $workdir/sources/$DIRECTORY/
        cp $tmpdir/$FILE $workdir/sources/$DIRECTORY/
      elif [[ $FILE == *tests ]]; then
        echo move $FILE to github
        mkdir -p $workdir/sources/$DIRECTORY/$FILE
        cp $tmpdir/$FILE/* $workdir/sources/$DIRECTORY/$FILE/
      elif [[ $FILE == names ]]; then
        echo move $FILE to s3
        s3cmd put setacl --acl-public $tmpdir/$FILE s3://goat/releases/$RELEASE/$DIRECTORY/ --recursive
      else
        # check if file has been updated since last release
        diff -q \
          <(s3cmd info s3://goat/sources/$DIRECTORY/$FILE || true | grep "MD5 sum" | awk '{print $NF}') \
          <(md5sum $tmpdir/$FILE | awk '{print $1}')
        if [ $? -ne 0 ]; then
          # update associated YAML file with release date
          YAML=$(basename $(grep -w $FILE $tmpdir/*.yaml | cut -d':' -f1))
          cat $tmpdir/$YAML | yq '.file.source_date="'${RELEASE//./-}'"' > $workdir/sources/$DIRECTORY/$YAML
        fi
        echo move $FILE to s3
        s3cmd put setacl --acl-public $tmpdir/$FILE s3://goat/releases/$RELEASE/$DIRECTORY/$FILE
      fi
    done < $tmpdir/from_resources.txt
    if [ -d $tmpdir/imported ]; then
      s3cmd put setacl --acl-public $tmpdir/imported s3://goat/releases/$RELEASE/$DIRECTORY/ --recursive
    fi
    if [ -d $tmpdir/exceptions ]; then
      s3cmd put setacl --acl-public $tmpdir/exceptions s3://goat/releases/$RELEASE/$DIRECTORY/ --recursive
    fi
  fi
else
  if [ ! -z "$RESOURCES" ]; then
    # restore indices from snapshot
    curl -s -X DELETE "es1:9200/$INDICES"
    curl -s -X POST   "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}/_restore?wait_for_completion=true&pretty" \
    -H 'Content-Type: application/json' \
    -d' { "indices": "'$INDICES'" }'
    # delete snapshot
    echo curl -s -X DELETE "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}"
  fi
  fail "Error while running genomehubs index"
fi

if [ ! -z "$RESOURCES" ]; then
  # delete snapshot
  curl -s -X DELETE "es1:9200/_snapshot/current/${RELEASE}_pre${DIRECTORY}"
fi

rm -rf $tmpdir