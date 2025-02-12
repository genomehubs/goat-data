#!/usr/bin/env python3

import os


def skip_prefect():
    """
    Skip Prefect imports if the environment variable is set.

    Returns:
        bool: True if the environment variable is set.
    """
    return os.environ.get("SKIP_PREFECT") == "true"


if skip_prefect():
    # Define dummy functions if Prefect is not installed

    def flow(*_, **__):
        return lambda x: x

    def task(*_, **__):
        return lambda x: x

    def emit_event(*_, **__):
        return lambda x: x

else:
    # Import Prefect functions if the environment variable is not set
    from prefect import flow, task
    from prefect.events import emit_event

__all__ = ["flow", "task", "emit_event"]
