"""This will access api _tools and _config modules.

Will generate .tsv files from api-retrieved data for GoaT import.
"""

import sys
import random
import requests
import time

import api_config as cfg
import api_tools as at

"""try to access each API 3 times in case of failure or timeout"""


def access_api_with_retries(
    url_opener,
    api_count_handler,
    row_handler,
    fieldnames,
    output_filename,
    token=None,
    retries=3,
):
    max_delay = 30
    for attempt in range(1, retries + 1):
        base = min(max_delay, 2 ** (attempt - 1))
        delay = random.uniform(0, base)
        try:
            at.get_from_source(
                url_opener,
                api_count_handler,
                row_handler,
                fieldnames,
                output_filename,
                token=token,
            )
            r = url_opener(token=token)
            if r.status_code == 200:
                return
        except (
            requests.ConnectionError,
            requests.HTTPError,
            requests.Timeout,
            requests.RequestException,
        ) as e:
            print(
                f"Connection error {e} occurred for attempt {attempt +1}/{retries} "
                f"of accessing API. Retrying in {delay:.1f} seconds..."
            )
            time.sleep(delay)
    raise Exception(f"Max retries for {output_filename} reached. Exiting.")


access_api_with_retries(
    cfg.vgl_url_opener,
    cfg.vgl_hub_count_handler,
    cfg.vgl_row_handler,
    cfg.vgl_fieldnames,
    f"{sys.argv[1]}/{cfg.vgl_output_filename}",
)
# access_api_with_retries(
#     cfg.nhm_url_opener,
#     cfg.nhm_api_count_handler,
#     cfg.nhm_row_handler,
#     cfg.nhm_fieldnames,
#     f"{sys.argv[1]}/{cfg.nhm_output_filename}",
# )
access_api_with_retries(
    cfg.sts_url_opener,
    cfg.sts_api_count_handler,
    cfg.sts_row_handler,
    cfg.sts_fieldnames,
    f"{sys.argv[1]}/{cfg.sts_output_filename}",
    token=sys.argv[2],
)
