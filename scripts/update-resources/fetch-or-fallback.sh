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

workdir=$(pwd)
tmpdir=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')

function fail {
    printf '%s\n' "$1" >&2
    cd $workdir
    rm -rf $tmpdir
    exit "${2-1}"
}

mkdir -p $RESOURCES

cd $tmpdir
echo "RUN $CMD"
eval "$CMD"
status=$?
cd -

exitcode=0

for url in ${FALLBACK//,/$IFS}; do
  cd $tmpdir
  filename=$(basename $url)
  if [ $status == 0 ]; then
    ls -al
    echo $url
    echo UPLOAD $filename to s3
    s3cmd put setacl --acl-public $filename $url ||
    echo FAILED
  else
    echo FAILED
    echo FETCH $filename from $url
    s3cmd get --force $url $filename || fail FAILED
  fi
  cd -
  echo MOVE $filename to $RESOURCES
  mv $tmpdir/$filename $RESOURCES/$filename
  if [[ ! -f $RESOURCES/$filename ]]; then 
     fail FAILED
  fi
done
echo DEL $tmpdir
rm -rf $tmpdir || fail FAILED
