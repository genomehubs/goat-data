#!/usr/bin/env python3
"""NCBI functions."""

import ujson
from tolkein import tofetch
from tolkein import tolog

LOGGER = tolog.logger(__name__)

GBIF_API = "https://www.gbif.org/api"


def fetch_gbif_taxlist(params):
    """Fetch gbif taxon entries."""
    limit = params.get("limit", 5)
    offset = params.get("offset", 0)
    highertaxon_key = params.get("root", None)
    url = (
        "%s/species/search?advanced=false&rank=SPECIES&rank=SUBSPECIES&status=ACCEPTED&status=DOUBTFUL"
        % GBIF_API
    )
    if highertaxon_key is not None:
        url += "&highertaxon_key=%s" % highertaxon_key
    url += "&limit=%d&offset=%d" % (limit, offset)
    page = tofetch.fetch_url(url)
    data = ujson.decode(page)
    # Log the first result to see what taxonomic information is included
    if data.get("results"):
        LOGGER.info("Taxonomic information in GBIF response: %s", data["results"][0])
    return data


def stream_gbif_taxa(root=None):
    """Stream gbif taxon entries."""
    params = {"root": root, "limit": 50, "offset": 0}
    data = {"results": [], "endOfRecords": False}
    while not data["endOfRecords"]:
        data = fetch_gbif_taxlist(params)
        for entry in data.get("results", []):
            yield (entry["key"], entry)
        params["offset"] += params["limit"]


def prepare_xref_rows(identifiers, meta):
    """Convert identifiers to a set of rows for output."""
    rows = []
    common = {"species": meta["species"]}
    if "family" in meta:
        common.update({"family": meta["family"]})
    if "subspecies" in meta:
        common.update({"subspecies": meta["subspecies"]})
    if "NCBI" in identifiers:
        common.update({"ncbiTaxonId": identifiers["NCBI"]["id"]})
    else:
        common.update({"gbifTaxonId": "GBIF:%s" % identifiers["GBIF"]["id"]})
    for db, entry in identifiers.items():
        row = {**common}
        row.update({"xref": "%s:%s" % (db, str(entry["id"]))})
        row.update({"sourceUrl": entry["url"]})
        row.update({"source": entry["source"]})
        row.update({"sourceSlug": entry["id"]})
        row.update({"sourceStub": entry["url"].replace(str(entry["id"]), "")})
        rows.append(row)
    return rows


def fetch_gbif_identifiers(taxon, *, xrefs=None):
    """Fetch gbif identifiers for a taxon."""
    if xrefs is None:
        xrefs = []
    xrefs = set(["NCBI"] + xrefs)
    url = "%s/wikidata/species/%s?locale=en" % (GBIF_API, str(taxon))
    page = tofetch.fetch_url(url)
    identifiers = {
        "GBIF": {
            "id": taxon,
            "url": "https://www.gbif.org/species/%s" % taxon,
            "source": "GBIF taxonKey",
        }
    }
    if page is not None:
        try:
            data = ujson.decode(page)
            for entry in data.get("identifiers", []):
                label = entry.get("label", {}).get("value", "None")
                db = label.split(" ")[0]
                if db in xrefs:
                    # Validate the identifier format
                    if db == "NCBI" and not entry["id"].isdigit():
                        LOGGER.warning("Invalid NCBI taxid format for taxon %s: %s", taxon, entry["id"])
                        continue
                    identifiers.update(
                        {db: {"id": entry["id"], "url": entry["url"], "source": label}}
                    )
            # Log if expected cross-references are missing
            missing_xrefs = xrefs - set(identifiers.keys())
            if missing_xrefs:
                LOGGER.info("Missing cross-references for taxon %s: %s", taxon, missing_xrefs)
        except Exception as e:
            LOGGER.error("Error processing cross-references for taxon %s: %s", taxon, str(e))
    else:
        LOGGER.warning("No response from Wikidata endpoint for taxon %s", taxon)
    return identifiers


def fetch_gbif_occurrences(taxon_key, limit=100):
    """Fetch occurrence data with geographic information for a taxon."""
    url = f"{GBIF_API}/occurrence/search?taxonKey={taxon_key}&limit={limit}"
    page = tofetch.fetch_url(url)
    if page is not None:
        data = ujson.decode(page)
        return data.get("results", [])
    return []


def prepare_occurrence_rows(occurrences, taxon_key):
    """Convert occurrence data to a standardized format."""
    rows = []
    for occurrence in occurrences:
        row = {
            "taxonKey": taxon_key,
            "occurrenceId": occurrence.get("key"),
            "decimalLatitude": occurrence.get("decimalLatitude"),
            "decimalLongitude": occurrence.get("decimalLongitude"),
            "country": occurrence.get("country"),
            "stateProvince": occurrence.get("stateProvince"),
            "locality": occurrence.get("locality"),
            "year": occurrence.get("year"),
            "month": occurrence.get("month"),
            "day": occurrence.get("day"),
            "basisOfRecord": occurrence.get("basisOfRecord"),
            "institutionCode": occurrence.get("institutionCode"),
            "collectionCode": occurrence.get("collectionCode"),
            "catalogNumber": occurrence.get("catalogNumber")
        }
        rows.append(row)
    return rows


def fetch_gbif_distribution(taxon_key):
    """Fetch distribution data for a taxon."""
    url = f"{GBIF_API}/species/{taxon_key}/distributions"
    page = tofetch.fetch_url(url)
    if page is not None:
        data = ujson.decode(page)
        return data.get("results", [])
    return []


def fetch_gbif_conservation_status(taxon_key):
    """Fetch conservation status data for a taxon."""
    url = f"{GBIF_API}/species/{taxon_key}/conservation"
    page = tofetch.fetch_url(url)
    if page is not None:
        data = ujson.decode(page)
        return data.get("results", [])
    return []


def fetch_gbif_ecological_data(taxon_key):
    """Fetch ecological data for a taxon."""
    url = f"{GBIF_API}/species/{taxon_key}/ecology"
    page = tofetch.fetch_url(url)
    if page is not None:
        data = ujson.decode(page)
        return data
    return {}


def prepare_distribution_rows(distributions, taxon_key):
    """Convert distribution data to a standardized format."""
    rows = []
    for dist in distributions:
        row = {
            "taxonKey": taxon_key,
            "locationId": dist.get("locationId"),
            "locality": dist.get("locality"),
            "country": dist.get("countryCode"),
            "establishmentMeans": dist.get("establishmentMeans"),
            "lifeStage": dist.get("lifeStage"),
            "occurrenceStatus": dist.get("occurrenceStatus"),
            "threatStatus": dist.get("threatStatus"),
            "source": dist.get("source")
        }
        rows.append(row)
    return rows


def prepare_conservation_rows(conservation_data, taxon_key):
    """Convert conservation status data to a standardized format."""
    rows = []
    for status in conservation_data:
        row = {
            "taxonKey": taxon_key,
            "status": status.get("status"),
            "source": status.get("source"),
            "criteria": status.get("criteria"),
            "year": status.get("year"),
            "region": status.get("region"),
            "category": status.get("category")
        }
        rows.append(row)
    return rows


def prepare_ecological_rows(ecological_data, taxon_key):
    """Convert ecological data to a standardized format."""
    rows = []
    if ecological_data:
        row = {
            "taxonKey": taxon_key,
            "habitat": ecological_data.get("habitat"),
            "lifeForm": ecological_data.get("lifeForm"),
            "trophicLevel": ecological_data.get("trophicLevel"),
            "pathway": ecological_data.get("pathway"),
            "source": ecological_data.get("source")
        }
        rows.append(row)
    return rows


def fetch_species_with_countries(batch_size=1000, offset=0):
    """Fetch species with country information in batches."""
    url = (
        f"{GBIF_API}/species/search"
        "?advanced=false"
        "&rank=SPECIES"
        "&status=ACCEPTED"
        f"&limit={batch_size}"
        f"&offset={offset}"
        "&hasCoordinate=true"  # Only species with coordinates
        "&hasGeospatialIssue=false"  # Exclude records with geospatial issues
    )
    
    try:
        page = tofetch.fetch_url(url)
        if page is not None:
            data = ujson.decode(page)
            return data.get("results", []), data.get("endOfRecords", True)
        return [], True
    except Exception as e:
        LOGGER.error("Error fetching species batch: %s", str(e))
        return [], True


def stream_species_with_countries():
    """Stream species with country information."""
    offset = 0
    batch_size = 1000
    end_of_records = False
    
    while not end_of_records:
        species_batch, end_of_records = fetch_species_with_countries(batch_size, offset)
        for species in species_batch:
            yield species
        offset += batch_size
        LOGGER.info("Processed %d species", offset)


def prepare_species_country_rows(species):
    """Convert species data with country information to rows."""
    rows = []
    for sp in species:
        row = {
            "taxonKey": sp.get("key"),
            "scientificName": sp.get("scientificName"),
            "canonicalName": sp.get("canonicalName"),
            "rank": sp.get("rank"),
            "status": sp.get("status"),
            "countries": sp.get("countries", []),
            "numOccurrences": sp.get("numOccurrences", 0),
            "numOccurrencesWithCoordinates": sp.get("numOccurrencesWithCoordinates", 0)
        }
        rows.append(row)
    return rows


def gbif_parser(_params, opts, *args, **kwargs):
    """Parse GBIF taxa, identifiers, and additional data."""
    parsed = []
    
    # Handle species with countries if requested
    if opts.get("include-species-countries", False):
        for species in stream_species_with_countries():
            parsed += prepare_species_country_rows([species])
    
    # Existing functionality
    for root in opts["gbif-root"]:
        for key, meta in stream_gbif_taxa(root):
            identifiers = fetch_gbif_identifiers(key, xrefs=opts["gbif-xref"])
            parsed += prepare_xref_rows(identifiers, meta)
            
            if opts.get("include-distribution", False):
                distributions = fetch_gbif_distribution(key)
                parsed += prepare_distribution_rows(distributions, key)
            
            if opts.get("include-conservation", False):
                conservation_data = fetch_gbif_conservation_status(key)
                parsed += prepare_conservation_rows(conservation_data, key)
            
            if opts.get("include-ecology", False):
                ecological_data = fetch_gbif_ecological_data(key)
                parsed += prepare_ecological_rows(ecological_data, key)
            
            if opts.get("include-occurrences", False):
                occurrences = fetch_gbif_occurrences(key, limit=opts.get("occurrence-limit", 100))
                parsed += prepare_occurrence_rows(occurrences, key)
    
    return parsed
