"""This will access api _tools and _config modules.

Will generate .tsv files from api-retrieved data for GoaT import.
"""


import sys
import api_tools as at
import api_config as cfg


at.get_from_source(
    cfg.vgl_url_opener,
    cfg.vgl_hub_count_handler,
    cfg.vgl_row_handler,
    cfg.vgl_fieldnames,
    f"{sys.argv[1]}/{cfg.vgl_output_filename}",
)

at.get_from_source(
    cfg.nhm_url_opener,
    cfg.nhm_api_count_handler,
    cfg.nhm_row_handler,
    cfg.nhm_fieldnames,
    f"{sys.argv[1]}/{cfg.nhm_output_filename}",
)

at.get_from_source(
    cfg.sts_url_opener,
    cfg.sts_api_count_handler,
    cfg.sts_row_handler,
    cfg.sts_fieldnames,
    f"{sys.argv[1]}/{cfg.sts_output_filename}",
    token=sys.argv[2],
)
