# goat-data

The goat-data repository holds scripts and configuration files to support the import of data from an S3 bucket at [goat.cog.sanger.ac.uk](https://goat.cog.sanger.ac.uk) into an elasticsearch datastore to support the Genomes on a Tree (GoaT) [web site](https://goat.genomehubs.org) and [API](https://goat.genomehubs.org/api-docs).

```
git clone https://github.com/genomehubs/goat-data.git

cd goat-data/sources

# Edit goat.yaml version and paths to match your installation
```

## Release pipeline

### 1. Fetch resources

Fetches files that can be automatically updated based on `curl`, API scripts and `genomehubs parse` commands. Updated files are moved to `/resources` on s3. If any fetches fail, the import will fallback to the previous version of the file on s3.

### 2. Init release

Initialises snapshot repositories and uses taxonomy files from `/resources` on s3 to initialise a new release with the `genomehubs init` command.

### 3. Index directories

Indexes files in subdirectories of `goat-data/sources` to populate the indexes using the `genomehubs index` command. For each subdirectory, two rounds of the import may be attempted. Each import is run in a separate temporary working directory, with files copied to destination paths on success.

### 3.1. Index files from s3 `/resources`

Before the first import round, a snapshot is made of the current state of all relevant indexes to allow the import to be rolled back on failure.

The first import fetches YAML configuration files from `goat-data/sources` and s3 `/resources`. For files found in both locations, the version in s3 `/resources` is used in preference.

Each YAML is parsed to find the associated data file under `.file.name`. This file is fetched from s3 `/resources` if possible or from s3 `/sources` if no matching file is found in `/resources`.
