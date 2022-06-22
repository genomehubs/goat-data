library(tidyverse)
library(janitor)

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
