#!/bin/bash

# get all taxids available on ena taxonomy download (these are the ones also in ncbi taxdump)
curl -s ftp://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz \
| gunzip -c | grep "^<taxon" | perl -lne 'print $1 if /taxId="(\d+)"/' > ena-taxonomy.xml.taxids

# get ALL ena taxids from ena api (these include the ones NOT in ncbi taxdump)
curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=taxon&query=tax_tree(2759)&limit=5000000" > resulttaxon.tax_tree2759.tsv

# if an extra.curr.tsv file exists, get all the taxids from it and rename it extra.prev.taxids
tail -n+2 resulttaxon.tax_tree2759.extra.curr.tsv | cut -f1 > resulttaxon.tax_tree2759.extra.prev.taxids

# remove ena taxonomy download IDs and extra.prev.taxids from the ena api tsv
cat ena-taxonomy.xml.taxids resulttaxon.tax_tree2759.extra.prev.taxids \
| fgrep -v -w -f - resulttaxon.tax_tree2759.tsv > resulttaxon.tax_tree2759.extra.curr.tsv

# if prev jsonl exists, only keep those entries which are in current resulttaxon.tax_tree2759.tsv
tail -n+2 resulttaxon.tax_tree2759.tsv \
| cut -f1 \
| perl -plne 's/(\d+)/"taxId" : "$1"/' \
| fgrep -f - ena-taxonomy.extra.jsonl \
> ena-taxonomy.extra.prev.jsonl

# download the extra ENA jsons
tail -n+2 resulttaxon.tax_tree2759.extra.curr.tsv | cut -f 1 \
| while read -r TAXID
do
  curl -s https://www.ebi.ac.uk/ena/taxonomy/rest/tax-id/$TAXID \
  | perl -lne '
    $jsonl = "" if /^{/;
    $jsonl .= $_;
    print $jsonl if /^}/
  '
done > ena-taxonomy.extra.curr.jsonl

cat ena-taxonomy.extra.prev.jsonl ena-taxonomy.extra.curr.jsonl > ena-taxonomy.extra.jsonl

