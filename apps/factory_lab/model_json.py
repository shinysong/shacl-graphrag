"""Bounded response syntax only; no schema, semantic repair or network."""
import json
import re

def decode_model_json(content):
    """Read JSON or one complete JSON fence; never repair or extract fragments.

    The original gateway message remains untouched in its durable call record.
    Schema, source-pointer and approval checks still apply to the decoded value.
    """
    if not isinstance(content, str) or len(content.encode()) > 256000:
        raise ValueError('Missing or oversized model JSON response')
    body = content.strip()
    envelope = 'json'
    if body.startswith('```'):
        match = re.fullmatch(r'```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```', body, re.IGNORECASE)
        if not match:
            raise ValueError('Model response is not valid JSON')
        body = match.group(1)
        envelope = 'json_fence'
    try:
        return json.loads(body), envelope
    except (ValueError, RecursionError) as exc:
        raise ValueError('Model response is not valid JSON') from exc

