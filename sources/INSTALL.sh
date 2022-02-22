# init
genomehubs init --config-file goat.yaml --taxonomy-ncbi-root 2759 --taxon-preload

# update ncbi datasets data
mkdir -p assembly-data && \
datasets download genome taxon "Eukaryota" --dehydrated --filename assembly-data/eukaryota.zip && \
unzip -o -d assembly-data assembly-data/eukaryota.zip ncbi_dataset/data/assembly_data_report.jsonl && \
genomehubs parse --ncbi-datasets assembly-data --outfile assembly-data/ncbi_datasets_eukaryota.tsv.gz

# update ncbi refseq organelles data
genomehubs parse --refseq-organelles --outfile assembly-data/refseq_organelles.tsv.gz

# update tolids data
mkdir -p tolids && \
curl https://gitlab.com/wtsi-grit/darwin-tree-of-life-sample-naming/-/raw/master/tolids.txt | gzip -c > tolids/tolids.tsv.gz && \

# index assembly-data and tolids and fill
genomehubs index --config-file goat.yaml --assembly-dir assembly-data
genomehubs index --config-file goat.yaml --taxon-dir    tolids          --taxon-lookup any
# index metadata in goat-data/sources and fill
genomehubs index --config-file goat.yaml --taxon-dir genome_size_chr_num --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir legislation         --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir target_lists        --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir regional            --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir chromosomes         --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir karyotype.org       --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --taxon-dir    btk              --taxon-lookup any --taxon-spellcheck
genomehubs index --config-file goat.yaml --assembly-dir btk              --taxon-lookup any --taxon-spellcheck

genomehubs fill  --config-file goat.yaml --traverse-root 2759 --traverse-infer-both

# snapshot
VERSION=2021.05.11
SNAPSHOT=fill
curl -X PUT "localhost:9200/_snapshot/snapshotrepo/snapshot_${VERSION}_${SNAPSHOT}?wait_for_completion=true&pretty" \
  -H 'Content-Type: application/json' \
  -d'{ "indices": "*--'$VERSION'", "include_global_state": false }'


