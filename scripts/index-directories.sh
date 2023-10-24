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

while read YAML; do
  YAMLFILE=$(basename $YAML)
  if [ ! -z "$RESOURCES" ]; then
    s3cmd get s3://goat/resources/$DIRECTORY/$YAMLFILE $tmpdir/$YAMLFILE 2>/dev/null
    if [ $? -ne 0 ]; then
      cp $YAML $tmpdir/$YAMLFILE
    fi
    FILE=$(cat $tmpdir/$YAMLFILE | yq -r '.file.name' 2>/dev/null)
    if [[ -z $FILE ]] || [[ "$FILE" == null ]]; then
      continue
    fi
    if [ -e "$RESOURCES/$DIRECTORY/$FILE" ]; then
      cp $RESOURCES/$DIRECTORY/$FILE $tmpdir/$FILE
    else
      s3cmd get s3://goat/resources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
      if [[ $? -ne 0 ]]; then
        s3cmd get s3://goat/sources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
      fi
    fi
  else
    cp $YAML $tmpdir/$YAMLFILE
    FILE=$(cat $tmpdir/$YAMLFILE | yq -r '.file.name' 2>/dev/null)
    if [[ -z $FILE ]] || [[ "$FILE" == null ]]; then
      continue
    fi
    s3cmd get s3://goat/sources/$DIRECTORY/$FILE $tmpdir/$FILE 2>/dev/null
  fi
  if [ ! -e "$tmpdir/$FILE" ]; then
    fail "unable to find data file $FILE required by $YAML"
  fi
done <<< $(ls sources/$DIRNAME/*types.yaml sources/$DIRNAME/*names.yaml 2>/dev/null)

echo docker run --rm --network=host \
    -v $tmpdir:/genomehubs/sources \
    genomehubs/genomehubs:$DOCKERVERSION bash -c \
        "genomehubs index \
        --es-host es1:9200 \
        --taxonomy-source $TAXONOMY \
        --config-file sources/goat.yaml \
        --es-version $RELEASE \
        --${TYPE}-dir sources $FLAGS"

rm -rf $tmpdir