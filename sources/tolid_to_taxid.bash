echo $1; echo `curl -s "localhost:3003/api/v0.0.1/lookup?searchTerm=$1&result=taxon&taxonomy=ncbi" | perl -lne 'print $1 if /taxon_id-(\d+)/'`
