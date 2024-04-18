#!/usr/bin/env python3
"""BlobToolKit functions."""


import contextlib

import ujson
from tolkein import tofetch, tolog

LOGGER = tolog.logger(__name__)

BTK_API = "https://blobtoolkit.genomehubs.org/api/v1"
BTK_VIEW = "https://blobtoolkit.genomehubs.org/view"


def fetch_btk_datasets(root):
    """Fetch BlobToolKit taxon entries."""
    url = f"{BTK_API}/search/{root}"
    page = tofetch.fetch_url(url)
    return ujson.decode(page)


def stream_btk_datasets(root="Eukaryota"):
    """Stream BlobToolKit taxon entries."""
    if datasets := fetch_btk_datasets(root):
        for dataset in datasets:
            yield dataset["id"], dataset


def extract_btk_stats(meta):
    """Extract BlobToolKit stats to top level."""
    summaryStats = meta.pop("summaryStats", {})
    meta["source"] = "BlobToolKit"
    meta["sourceSlug"] = meta["id"]
    meta["sourceStub"] = "https://blobtoolkit.genomehubs.org/view/dataset/"
    # meta["xref"] = "BTK:%s" % meta["id"]
    if "busco" in summaryStats:
        for busco_lineage, busco_stats in summaryStats["busco"].items():
            meta["busco_lineage"] = busco_lineage
            meta["busco_string"] = busco_stats["string"]
            meta["busco_complete"] = busco_stats["c"] / busco_stats["t"] * 100
            break
    if "stats" in summaryStats:
        meta["nohit"] = summaryStats["stats"]["noHit"] * 100
        with contextlib.suppress(KeyError):
            meta["target"] = summaryStats["stats"]["target"] * 100
    if "baseComposition" in summaryStats:
        meta["at_percent"] = summaryStats["baseComposition"]["at"] * 100
        meta["gc_percent"] = summaryStats["baseComposition"]["gc"] * 100
        meta["n_percent"] = summaryStats["baseComposition"]["n"] * 100
    try:
        if len(meta["taxon_name"]) > len(meta["species"]):
            meta["subspecies"] = meta["taxon_name"]
    except KeyError:
        meta["species"] = meta["taxon_name"]


def describe_btk_files(meta):
    """Generate analysis descriptions and links for BlobToolKit."""
    plots = ["cumulative", "snail"]
    summaryStats = meta.get("summaryStats", {})
    if "readMapping" in summaryStats and summaryStats["readMapping"]:
        plots.append("blob")
    files = []
    for plot in plots:
        print(plots)
        if plot == "blob":
            url = f'{BTK_API}/image/{meta["id"]}/{plot}/circle?format=png'
        else:
            url = f'{BTK_API}/image/{meta["id"]}/{plot}?format=png'
        obj = {
            "name": f"{plot}.png",
            "url": url,
            "source_url": f'{BTK_VIEW}/{meta["id"]}/dataset/{meta["id"]}/{plot}',
            "analysis_id": f'btk-{meta["id"]}',
            "description": f'a {plot} plot from BlobToolKit analysis {meta["id"]}',
            "title": f'{plot} plot {meta["id"]}',
            "command": "blobtoolkit pipeline",
            "assembly_id": meta["accession"],
            "taxon_id": str(meta["taxid"]),
            "analysis": {
                "name": "BlobToolKit",
                "title": f'BlobToolKit analysis of {meta["accession"]}',
                "description": (
                    f'Analysis of public assembly {meta["accession"]} '
                    f"using BlobToolKit"
                ),
                "source": "BlobToolKit",
                "source_url": (
                    f"https://blobtoolkit.genomehubs.org/view/dataset/" f'{meta["id"]}'
                ),
            },
        }
        files.append(obj)
    return files


def btk_parser(_params, opts, *args, **kwargs):
    """Parse BlobToolKit assemblies."""
    parsed = []
    analyses = []
    print(opts)
    for root in opts["btk-root"]:
        for key, meta in stream_btk_datasets(root):
            print(key)
            files = describe_btk_files(meta)
            analyses += files
            extract_btk_stats(meta)
            parsed.append(meta)
    return (parsed, analyses)


def main():
    pass


if __name__ == "__main__":
    main()
