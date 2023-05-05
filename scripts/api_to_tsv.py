import api_tools as at
import api_config as cfg
import sys

at.get_from_source(
    cfg.vgl_url_opener, 
    cfg.vgl_hub_count_handler, 
    cfg.vgl_row_handler, 
    cfg.vgl_fieldnames,
    cfg.vgl_output_filename
)

at.get_from_source(
    cfg.nhm_url_opener, 
    cfg.nhm_api_count_handler, 
    cfg.nhm_row_handler, 
    cfg.nhm_fieldnames,
    cfg.nhm_output_filename
)

at.get_from_source(
    cfg.sts_url_opener, 
    cfg.sts_api_count_handler, 
    cfg.sts_row_handler, 
    cfg.sts_fieldnames,
    cfg.sts_output_filename,
    token=sys.argv[1],
)

# at.get_from_source(
#     cfg.jgi_url_opener, 
#     cfg.jgi_api_count_handler, 
#     cfg.jgi_row_handler, 
#     cfg.jgi_fieldnames,
#     cfg.jgi_output_filename,
#     token=sys.argv[2],
# )