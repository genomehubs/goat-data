library(tidyverse)
library(janitor)
library(googlesheets4)

# dtol plant c values Sahr Mian
read_tsv("https://docs.google.com/spreadsheets/d/e/2PACX-1vSt0R1T3MpoOM6UFNMaT_Q9gR5TYyUZC1wgLqW_6_cH9zzII8ehadrbHX8bpktjTv2_yt_KHaj3x_e1/pub?output=tsv",
    col_types = "c") %>%
  clean_names() %>% remove_empty() %>%
  filter(!is.na(genus), project=="DTOL") %>%
  add_column(primary = 1) -> kew

write_tsv(kew, "./sources/genomesize_karyotype/DTOL_Plant_Genome_Size_Estimates.tsv")


# shane's tolqc status - select length if available, else est_size
read_tsv("https://docs.google.com/spreadsheets/d/e/2PACX-1vTU-En_URbYPtfyjBueQhnz7wYHt-OHVxvRyv9tNvCUPCTX9EEzxOL41QCUh6hgVNv-Vv_gLSAMJXv-/pub?gid=1442224132&single=true&output=tsv",
    na = c("NA", "missing","","NULL")) %>%
  clean_names() %>% remove_empty() %>%
  filter(!is.na(taxon)) %>%
  filter(is.na(accession) | !str_detect(accession, "^GCA_")) %>%
  filter(!str_detect(statussummary, "^9")) %>%
  filter(!str_detect(statussummary, "^5")) %>%
  select(taxon, est_size_mb, length_mb) %>%
  mutate(across(c(est_size_mb, length_mb), as.numeric)) %>%
  filter(!is.na(est_size_mb) | !is.na(length_mb)) -> tolqc

write_tsv(tolqc, "./sources/genomesize_karyotype/DTOL_assembly_informatics_status_kmer_draft.tsv")

# CNGB
read_tsv("https://docs.google.com/spreadsheets/d/e/2PACX-1vQeTqi-qnoNgNl58gWDBT4CcR8nF9SmFOkC82KC6pkH42CoEi94yInhBE25SfxBqNeMBeVbpeEVs9GI/pub?gid=1726876704&single=true&output=tsv",
    na = c("NA", "missing","","NULL")) %>%
  remove_empty() -> cngb

write_tsv(cngb, "./sources/assembly-data/cngb.tsv")

# australian bioportal
# read_tsv("https://docs.google.com/spreadsheets/u/1/d/e/2PACX-1vS4iAxznp7djwBZE-m00ggKoVw8TZgxn19Lz1nYU20h_gYBARFd9ZS1zAjRpQlPE-68XK6zHKFfe4UA/pub?gid=890267489&output=tsv") %>%
#   clean_names() %>% remove_empty() %>% lapply(function(x) iconv(x, "latin1", "ASCII", sub="")) %>% as_tibble() %>%
#   select(bioplatforms_initiative, genus, species, subspecies, taxonomic_family_example_hominidae, ncbi_taxon_id, sequencing_status) %>%
#   mutate(bioplatforms_initiative = ifelse(bioplatforms_initiative == "Australian Grasslands", "AGI", bioplatforms_initiative)) %>%
#   mutate(bioplatforms_initiative = ifelse(bioplatforms_initiative %in% c("Wheat","Wine"), "GAP", bioplatforms_initiative)) %>%
#   filter(bioplatforms_initiative %in% c("OMG","ARG","TSI","GAP","GBR","AGI")) %>%
#   mutate(sequencing_status = ifelse(sequencing_status %in% c("complete","in progress"), "in_progress","")) %>%
#   mutate(in_progress = ifelse(sequencing_status == "in_progress",bioplatforms_initiative,"")) %>%
#   mutate(sample_acquired = ifelse(sequencing_status == "in_progress",bioplatforms_initiative,"")) %>%
#   mutate(sample_collected = ifelse(sequencing_status == "in_progress",bioplatforms_initiative,"")) %>%
#   mutate(target_status = "other_priority", long_list = bioplatforms_initiative, other_priority = bioplatforms_initiative) %>%
#   mutate(sequencing_status_omg = ifelse(bioplatforms_initiative == "OMG", sequencing_status,"")) %>%
#   mutate(sequencing_status_arg = ifelse(bioplatforms_initiative == "ARG", sequencing_status,"")) %>%
#   mutate(sequencing_status_tsi = ifelse(bioplatforms_initiative == "TSI", sequencing_status,"")) %>%
#   mutate(sequencing_status_gap = ifelse(bioplatforms_initiative == "GAP", sequencing_status,"")) %>%
#   mutate(sequencing_status_gbr = ifelse(bioplatforms_initiative == "GBR", sequencing_status,"")) %>%
#   mutate(sequencing_status_agi = ifelse(bioplatforms_initiative == "AGI", sequencing_status,"")) %>%
#   write_tsv("./sources/status_lists/Aus_Genome_status_Bioplatforms.tsv")