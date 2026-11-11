"""Versioned model-facing evidence; transport details remain in audit records."""
import json

CONTRACT = 'factory-evidence-v1'
FIELDS = ('evidence_id', 'tool', 'arguments', 'snapshot', 'source_sha256',
          'as_of', 'rows', 'scope', 'limit_reached')


def model_evidence(result):
    """Project successful tool output without changing row order or evidence scope."""
    return {key: result[key] for key in FIELDS if key in result}


def canonical(value):
    """Object key order is not an experimental treatment; array order is retained."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
