#!/usr/bin/env python3

import blobtk
from prefect import flow, task


@task
def validate_data(data):
    if data:
        return True
    return False


@task
def process_data(data):
    return data


@flow
def validation_flow(data):
    valid = validate_data(data)
    return process_data(valid)
