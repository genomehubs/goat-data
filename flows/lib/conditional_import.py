#!/usr/bin/env python3

import os

if os.environ.get("SKIP_PREFECT") == "true":

    def flow(*_, **__):
        return lambda x: x

    def task(*_, **__):
        return lambda x: x

    def emit_event(*_, **__):
        return lambda x: x

else:
    from prefect import flow, task
    from prefect.events import emit_event

__all__ = ["flow", "task", "emit_event"]
