"""Connect to Exasol: nocertcheck for Exasol Personal on this machine, the certificate fingerprint for anything else."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pyexasol

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def dsn() -> str:
    value = os.environ.get("EXASOL_DSN", "127.0.0.1:8563")
    if "/" in value:  # already host/FINGERPRINT:port or host/nocertcheck:port
        return value
    host, _, port = value.rpartition(":")
    fingerprint = os.environ.get("EXASOL_FINGERPRINT", "").replace(":", "").strip()
    if fingerprint:
        return f"{host}/{fingerprint}:{port}"
    if host in LOCAL_HOSTS:
        # Exasol Personal local signs its own certificate; its connection instructions say to use nocertcheck.
        return f"{host}/nocertcheck:{port}"
    raise RuntimeError(f"{host} is not this machine: set EXASOL_FINGERPRINT to the certificate fingerprint\n"
                       "from your deployment's connection-instructions.txt.")


def password() -> str:
    if os.environ.get("EXASOL_PASSWORD"):
        return os.environ["EXASOL_PASSWORD"]
    secrets = Path.home() / ".exasol/personal/deployments/default/secrets.json"
    if secrets.exists():
        return json.loads(secrets.read_text(encoding="utf-8"))["dbPassword"]
    raise RuntimeError("Set EXASOL_PASSWORD (it is in secrets.json in your Exasol Personal deployment directory).")


def connect() -> pyexasol.ExaConnection:
    try:
        return pyexasol.connect(dsn=dsn(), user=os.environ.get("EXASOL_USER", "sys"),
                                password=password(), autocommit=True, client_name="exacademy-dashboard",
                                fetch_mapper=pyexasol.exasol_mapper)  # DECIMAL -> Decimal, TIMESTAMP -> datetime
    except pyexasol.ExaError as e:
        raise RuntimeError(f"Cannot connect to Exasol: {str(e).strip().splitlines()[0]}") from None


def connect_or_exit() -> pyexasol.ExaConnection:
    try:
        return connect()
    except RuntimeError as e:
        sys.exit(str(e))
