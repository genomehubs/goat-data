#!/bin/bash

mkdir /tmp/ena-taxonomy
cd /tmp/ena-taxonomy
wget ftp://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz

gunzip -c taxonomy.xml.gz | grep "^<taxon" | perl -lne 'print $1 if /taxId="(\d+)"/' > ena.taxonomy.xml.taxids
curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=taxon&query=tax_tree(2759)&limit=5000000" > resulttaxon.tax_tree2759.tsv

# remove taxonomy.xml taxids

fgrep -v -w -f ena.taxonomy.xml.taxids resulttaxon.tax_tree2759.tsv > resulttaxon.tax_tree2759.extra.curr.tsv
wc -l resulttaxon.tax_tree2759.extra.curr.tsv

tail -n+2 resulttaxon.tax_tree2759.extra.curr.tsv \
| while IFS=$'\t' read -r TAXID DESC
do
  curl -s https://www.ebi.ac.uk/ena/taxonomy/rest/tax-id/$TAXID \
  | perl -lne '
    $jsonl = "" if /^{/;
    $jsonl .= $_;
    print $jsonl if /^}/
  '
done > ena-taxonomy.extra.jsonl

# convert 3 part scientific name jsonl subspecies entries to include species as parent:

perl -i -plne 's/(.*scientificName\" : \"(\S+) (\S+) .*?\".*\"subspecies\".*?lineage\" : \".*?)( \".*)/$1 $2 $3;$4/' ena-taxonomy.extra.jsonl

perl -lne 'print unless /scientificName\" : \"((\S+?)\s+(\S+?)\s+(.+?))\".*\"subspecies\"/ and (scalar split(/\s+/,$1) !=3 and $4!~/^(var|ssp|subsp)/)' ena-taxonomy.extra.jsonl | grep -v -w 1676804 | grep Eukaryota > tmp

mv tmp ena-taxonomy.extra.jsonl
