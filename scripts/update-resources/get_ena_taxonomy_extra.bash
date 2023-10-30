#!/bin/bash

TAXROOT=$1
if [ -z $TAXROOT ]; then
    TAXROOT=2759
fi

# get all taxids available on ena taxonomy download (these are the ones also in ncbi taxdump)
curl -Ls https://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz \
| gunzip -c | grep "^<taxon" | perl -lne 'print $1 if /taxId="(\d+)"/' > ena-taxonomy.xml.taxids || echo "Unable to fetch taxonomy xml" || exit 0

if [ $(stat -c %s ena-taxonomy.xml.taxids) -lt 10000000 ]; then 
  echo "Unable to fetch taxonomy"
  exit 0;
fi

# get ALL ena taxids from ena api (these include the ones NOT in ncbi taxdump)
curl -Ls "https://www.ebi.ac.uk/ena/portal/api/search?result=taxon&query=tax_tree($TAXROOT)&limit=10000000" > resulttaxon.tax_tree$TAXROOT.taxid_desc || \
echo "Unable to fetch taxids" || \
exit 1

if [ $(stat -c %s resulttaxon.tax_tree$TAXROOT.taxid_desc) -lt 21 ]; then 
  echo "No taxids in file"
  exit 0;
fi

# taxids may be in column 1 or 2 - check which before cutting!
if [[ "$(head -n 1 resulttaxon.tax_tree$TAXROOT.taxid_desc | cut -f1)" == tax_id ]]; then
  cut -f1 resulttaxon.tax_tree$TAXROOT.taxid_desc > resulttaxon.tax_tree$TAXROOT.taxids
elif [[ "$(head -n 1 resulttaxon.tax_tree$TAXROOT.taxid_desc | cut -f2)" == tax_id ]]; then
  cut -f2 resulttaxon.tax_tree$TAXROOT.taxid_desc > resulttaxon.tax_tree$TAXROOT.taxids
else
  echo "ERROR: Taxid list is not a valid format"
  head -n 2 resulttaxon.tax_tree$TAXROOT.taxid_desc
  exit 1
fi

# if prev extra jsonl exists, gunzip it first
gunzip ena-taxonomy.extra.$TAXROOT.prev.jsonl.gz 2>/dev/null
if [[ $? -eq 0 ]]; then
  # then only keep those entries which are in current resulttaxon.tax_tree$TAXID.tsv
  tail -n+2 resulttaxon.tax_tree$TAXROOT.taxids \
  | perl -plne 's/(\d+)/"taxId" : "$1"/' \
  | fgrep -f - ena-taxonomy.extra.$TAXROOT.jsonl \
  > TMP && mv TMP ena-taxonomy.extra.$TAXROOT.prev.jsonl
else
  echo "No previous jsonl file found" || \
  touch ena-taxonomy.extra.$TAXROOT.prev.jsonl
fi

# get taxids from ena-taxonomy.extra.prev.jsonl (these don't need to be downloaded again)
perl -plne 's/.*\"taxId\" : "(\d+)\".*/$1/' ena-taxonomy.extra.$TAXROOT.prev.jsonl > ena-taxonomy.extra.$TAXROOT.prev.taxids

# remove prev ena jsonl, ftp taxonomy download IDs, and extra.prev.taxids from the ena api tsv
cat ena-taxonomy.extra.$TAXROOT.prev.taxids ena-taxonomy.xml.taxids \
| fgrep -v -w -f - resulttaxon.tax_tree$TAXROOT.taxids > resulttaxon.tax_tree$TAXROOT.extra.curr.taxids

# download the extra ENA jsons
tail -n+2 resulttaxon.tax_tree$TAXROOT.extra.curr.taxids \
| while read -r TAXID
do
  curl -s https://www.ebi.ac.uk/ena/taxonomy/rest/tax-id/$TAXID \
  | perl -lne '
    $jsonl = "" if /^{/;
    $jsonl .= $_;
    print $jsonl if /^}/
  '
done > ena-taxonomy.extra.$TAXROOT.curr.jsonl

# cat the prev and curr jsonl, but sort by length of lineage:
cat ena-taxonomy.extra.$TAXROOT.prev.jsonl ena-taxonomy.extra.$TAXROOT.curr.jsonl \
| perl -lne '
{
  $jsonl = $_;
  $lineage = $1 if /"lineage" : "(.+?)"/;
  $lineage_count = ($lineage =~ s/;/;/g);
  $jsonl_hash{$jsonl} = $lineage_count;
}
END
{
  foreach my $jsonl (sort { $jsonl_hash{$a} <=> $jsonl_hash{$b} } keys %jsonl_hash) {
    print $jsonl;
  }
}' > ena-taxonomy.extra.$TAXROOT.jsonl

gzip ena-taxonomy.extra.$TAXROOT.jsonl
