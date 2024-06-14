#!/bin/bash

YAMLFILE=/Users/rchallis/projects/genomehubs/goat-data/sources/assembly-data/1kfg_manual_bioprojects.types.yaml
FILE=$(cat $YAMLFILE | yq -r '.file.name')

if [[ -z $FILE ]] || [[ "$FILE" == null ]]; then
   echo "No file specified in YAML"
else
  echo file is $FILE
fi