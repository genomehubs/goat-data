#!/bin/bash

workdir=$(pwd)
tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')

function fail {
    printf '%s\n' "$1" >&2
    cd $workdir
    rm -rf $tmpdir
    exit "${2-1}"
}

DIRNAME=$(if [[ -d sources/$DIRECTORY ]]; then echo $DIRECTORY; else echo ${DIRECTORY//-/_}; fi)

> $tmpdir/from_resources.txt

# List YAML files available in sources and on S3
SUFFIX=.yaml
SOURCEYAMLS=$(ls sources/$DIRNAME/*types$SUFFIX sources/$DIRNAME/*names$SUFFIX 2>/dev/null);
S3YAMLS=$(s3cmd ls s3://goat/resources/$DIRNAME --recursive | grep $SUFFIX | awk '{print $NF}' 2>/dev/null)
S3YAMLS=$(grep -vFf <(echo "$SOURCEYAMLS" | awk -F"/" '{print $NF}') <(echo "$S3YAMLS") 2>/dev/null)

# Loop through YAMLs fetching YAML and data from S3 if available else from sources
while read YAML; do
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
done <<< $(printf "$SOURCEYAMLS\n$S3YAMLS\n" | sed '/^$/d')

# Fetch names directory
if [ ! -z "$RESOURCES" ]; then
  s3cmd get s3://goat/resources/$DIRECTORY/names $tmpdir/names 2>/dev/null
  if [ $? -eq 0 ]; then
    echo names >> $tmpdir/from_resources.txt
    # Add extra files from sources
    while read FILE; do
      if [ ! -e "$tmpdir/names/$FILE" ]; then
        cp sources/$DIRNAME/names/$FILE $tmpdir/names/
      fi
    done <<< $(ls sources/$DIRNAME/lineage_tests 2>/dev/null)
  else
    s3cmd get s3://goat/sources/$DIRECTORY/names $tmpdir/names 2>/dev/null
  fi
else
  s3cmd get s3://goat/sources/$DIRECTORY/names $tmpdir/names 2>/dev/null
fi

# Fetch tests directory
if [ ! -z "$RESOURCES" ]; then
  s3cmd get s3://goat/resources/$DIRECTORY/tests $tmpdir/tests 2>/dev/null
  if [ $? -eq 0 ]; then
    echo tests >> $tmpdir/from_resources.txt
    # Add extra tests from sources
    while read YAML; do
      if [ ! -e "$tmpdir/tests/$YAML" ]; then
        cp sources/$DIRNAME/tests/$YAML $tmpdir/tests/
      fi
    done <<< $(ls sources/$DIRNAME/lineage_tests 2>/dev/null)
  else
    cp -r sources/$DIRNAME/tests $tmpdir/tests 2>/dev/null
  fi
else
  cp -r sources/$DIRNAME/tests $tmpdir/tests 2>/dev/null
fi

# Run genomehubs index on the collated files
docker run --rm --network=host \
    -v $tmpdir:/genomehubs/sources \
    genomehubs/genomehubs:$DOCKERVERSION bash -c \
        "genomehubs index \
        --es-host es1:9200 \
        --taxonomy-source $TAXONOMY \
        --config-file sources/goat.yaml \
        --es-version $RELEASE \
        --${TYPE}-dir sources $FLAGS"

# If index was successful, move files from resources to release branch/bucket
if [ $? -eq 0 ]; then
  echo Reading $(wc -l $tmpdir/from_resources.txt) files to move from $tmpdir/from_resources.txt
  while read FILE; do
    if [ $FILE == *yaml ]; then
      echo move $FILE to github
    elif [ $FILE == tests ]; then
      echo move $FILE to github
    else
      echo move $FILE to s3
    fi
  done < $tmpdir/from_resources.txt
else
  fail "Error while running genomehubs index"
fi

rm -rf $tmpdir