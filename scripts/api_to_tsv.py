import api_tools as at
import api_config as cfg


at.get_from_source(
    cfg.vgl_url, 
    cfg.vgl_hub_count_handler, 
    cfg.vgl_row_handler, 
    cfg.vgl_fieldnames,
    cfg.vgl_output_filename
)

at.get_from_source(
    cfg.nhm_url, 
    cfg.nhm_api_count_handler, 
    cfg.nhm_row_handler, 
    cfg.nhm_fieldnames,
    cfg.nhm_output_filename
)