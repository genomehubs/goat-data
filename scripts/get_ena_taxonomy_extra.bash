#!/bin/bash

TAXROOT=$1
if [ -z $TAXROOT ]; then
    TAXROOT=2759
fi

# get all taxids available on ena taxonomy download (these are the ones also in ncbi taxdump)
curl -s ftp://ftp.ebi.ac.uk/pub/databases/ena/taxonomy/taxonomy.xml.gz \
| gunzip -c | grep "^<taxon" | perl -lne 'print $1 if /taxId="(\d+)"/' > ena-taxonomy.xml.taxids

if [ $(stat -c %s ftp-taxonomy.taxids) -lt 10000000 ]; then exit 0; fi

# get ALL ena taxids from ena api (these include the ones NOT in ncbi taxdump)
curl -s "https://www.ebi.ac.uk/ena/portal/api/search?result=taxon&query=tax_tree($TAXROOT)&limit=10000000" | cut -f1 > resulttaxon.tax_tree$TAXROOT.taxids

if [ $(stat -c %s resulttaxon.tax_tree$TAXROOT.taxids) -lt 10000000 ]; then exit 0; fi

# if prev extra jsonl exists, gunzip it first
gunzip ena-taxonomy.extra.jsonl.gz

# then only keep those entries which are in current resulttaxon.tax_tree$TAXID.tsv
tail -n+2 resulttaxon.tax_tree$TAXROOT.taxids \
| perl -plne 's/(\d+)/"taxId" : "$1"/' \
| fgrep -f - ena-taxonomy.extra.jsonl \
> ena-taxonomy.extra.prev.jsonl

# get taxids from ena-taxonomy.extra.prev.jsonl (these don't need to be downloaded again)
perl -plne 's/.*\"taxId\" : "(\d+)\".*/$1/' ena-taxonomy.extra.prev.jsonl > ena-taxonomy.extra.prev.taxids

# remove prev ena jsonl, ftp taxonomy download IDs, and extra.prev.taxids from the ena api tsv
cat ena-taxonomy.extra.prev.taxids ena-taxonomy.xml.taxids \
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
done > ena-taxonomy.extra.curr.jsonl

# cat the prev and curr jsonl, but sort by length of lineage:
cat ena-taxonomy.extra.prev.jsonl ena-taxonomy.extra.curr.jsonl \
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
}' > ena-taxonomy.extra.jsonl

gzip ena-taxonomy.extra.jsonl
