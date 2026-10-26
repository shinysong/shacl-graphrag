"""Verify the complete reviewed ERP schema bundle before using any schema.

Offline integrity checking against a repository pin, not upstream authenticity
or business truth verification. Change the pin only through a fresh review.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

PIN_PATH = Path(__file__).resolve().parents[1] / 'research/sources/erpnext-procurement.json'


def _read_regular(path, limit):
    # Linux host: refuse symlinks at open, do not block opening a FIFO, and
    # inspect the actual descriptor rather than a prior pathname stat.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError('Expected a regular file: ' + str(path)) from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Expected a regular file: ' + str(path))
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        payload = b''.join(chunks)
    finally:
        os.close(fd)
    if len(payload) > limit:
        raise ValueError('File exceeds the byte limit: ' + str(path))
    return payload


def validate_snapshot(directory):
    directory = Path(directory)
    pin = json.loads(PIN_PATH.read_text())
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(_read_regular(manifest_path, 1_000_000))
    if not isinstance(manifest, dict):
        raise ValueError('Source manifest must be an object.')
    for field in ['source', 'branch', 'commit']:
        if manifest.get(field) != pin[field]:
            raise ValueError('Source pin mismatch: ' + field)
    records = manifest.get('records')
    expected = {record['path']: record for record in pin['records']}
    if not isinstance(records, list) or len(records) != len(expected):
        raise ValueError('Manifest must contain exactly the required schemas and license.')
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('path'), str):
            raise ValueError('Invalid manifest record.')
        path = record['path']
        if path not in expected or path in seen or 'error' in record:
            raise ValueError('Missing, duplicate, unexpected or failed source record.')
        seen.add(path)
        for field in ['saved_as', 'url', 'sha256', 'bytes']:
            if record.get(field) != expected[path][field]:
                raise ValueError('Source record does not match reviewed pin: ' + field)
    # All metadata is validated first; filenames come from the reviewed pin.
    # Return the verified bytes so callers do not reopen unchecked schema files.
    payloads = {}
    for record in pin['records']:
        filename = record['saved_as']
        path = directory / filename
        payload = _read_regular(path, record['bytes'])
        if len(payload) != record['bytes'] or hashlib.sha256(payload).hexdigest() != record['sha256']:
            raise ValueError('Source bytes differ from reviewed pin: ' + filename)
        payloads[filename] = payload
    return manifest, payloads
