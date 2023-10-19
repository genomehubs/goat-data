#!/bin/bash

usage='
    CMD="curl -Ls https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/linux-amd64/datasets > datasets" \
    FALLBACK=s3://goat/resources/datasets \
    RESOURCES=./resources \
    '$0

echo CMD=$CMD
echo FALLBACK=$FALLBACK
echo RESOURCES=$RESOURCES

if [[ -z "$CMD" ]] || [[ -z "$FALLBACK" ]] || [[ -z "$RESOURCES" ]]; then
    echo "USAGE: $usage"
    exit 1
fi

mkdir -p $RESOURCES
filename=$(basename $FALLBACK)

tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')
cd $tmpdir
echo "RUN $CMD"
eval "$CMD"
if [ $? == 0 ]; then
  echo UPLOAD $filename to s3
  s3cmd put setacl --acl-public $filename $FALLBACK ||
  echo FAILED
else
  echo FAILED
  echo FETCH $filename from $FALLBACK
  s3cmd get $FALLBACK $filename ||
  echo FAILED &&
  exit 1
fi
cd -
echo MOVE $filename to $RESOURCES
mv $tmpdir/$filename $RESOURCES/$filename
if [[ ! -f $RESOURCES/$filename ]]; then 
  echo FAILED &&
  exit 1
fi
echo DEL $tmpdir
rm -rf $tmpdir ||
echo FAILED




