"""Source-only reversible cell encoding. No retrieval, repair, or corpus lookup."""
import copy
import hashlib
import json

VERSION = "compact-cell-1"
FIELDS = ["cell", "data_type", "value", "formula", "cached_value"]


class RepresentationError(ValueError):
    """Caller must retain failure; never skip/refill or use raw fallback."""
    def __init__(self, status, detail):
        self.status = status
        super().__init__(detail)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON")


def _original(chunk):
    if type(chunk) is not dict or chunk.get("chunk_type") not in ("node", "edge"):
        raise ValueError("unsupported chunk")
    kind = chunk["chunk_type"]
    identifier = "node_id" if kind == "node" else "edge_id"
    if set(chunk) != {"chunk_id", "chunk_type", identifier, "text"}:
        raise ValueError("unexpected chunk fields")
    if any(type(chunk[key]) is not str or not chunk[key] for key in chunk):
        raise ValueError("chunk fields must be nonempty strings")
    if kind == "edge":
        canonical(chunk)
        return None
    record = json.loads(chunk["text"], object_pairs_hook=_pairs,
                        parse_constant=_constant)
    if type(record) is not dict or canonical(record).decode() != chunk["text"]:
        raise ValueError("noncanonical record")
    _transform(copy.deepcopy(record), False)
    return record


def _transform(record, decoding):
    def cells(rows):
        if type(rows) is not list:
            raise ValueError("cells must be list")
        result = []
        for cell in rows:
            if decoding:
                if type(cell) is not list or len(cell) != len(FIELDS):
                    raise ValueError("invalid cell array")
                result.append(dict(zip(FIELDS, cell)))
            else:
                if type(cell) is not dict or set(cell) != set(FIELDS):
                    raise ValueError("invalid cell fields")
                result.append([cell[key] for key in FIELDS])
        return result
    record["cells"] = cells(record["cells"])
    if type(record["header_rows"]) is not list:
        raise ValueError("headers must be list")
    for header in record["header_rows"]:
        if type(header) is not dict:
            raise ValueError("header must be object")
        header["cells"] = cells(header["cells"])
    return record


def encode(chunk):
    try:
        record = _original(chunk)
        digest = hashlib.sha256(canonical(chunk)).hexdigest()
        if chunk["chunk_type"] == "edge":
            return dict(projection_version=VERSION, raw_chunk_sha256=digest,
                        raw_chunk=copy.deepcopy(chunk))
        return dict(projection_version=VERSION, raw_chunk_sha256=digest,
                    identity={k: v for k, v in chunk.items() if k != "text"},
                    cell_fields=list(FIELDS),
                    record=_transform(copy.deepcopy(record), False))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise RepresentationError("unsupported_source_representation", str(exc)) from exc


def decode(payload):
    try:
        if type(payload) is not dict or payload.get("projection_version") != VERSION:
            raise ValueError("invalid version")
        if "raw_chunk" in payload:
            if set(payload) != {"projection_version", "raw_chunk_sha256", "raw_chunk"}:
                raise ValueError("unexpected edge wrapper fields")
            chunk = copy.deepcopy(payload["raw_chunk"])
            if type(chunk) is not dict or chunk.get("chunk_type") != "edge":
                raise ValueError("expected edge")
        else:
            if set(payload) != {"projection_version", "raw_chunk_sha256",
                                "identity", "cell_fields", "record"}:
                raise ValueError("unexpected node wrapper fields")
            if type(payload["cell_fields"]) is not list or payload["cell_fields"] != FIELDS:
                raise ValueError("field order mismatch")
            identity = payload["identity"]
            if (type(identity) is not dict or set(identity) !=
                    {"chunk_id", "chunk_type", "node_id"} or identity["chunk_type"] != "node"):
                raise ValueError("invalid identity")
            record = copy.deepcopy(payload["record"])
            if type(record) is not dict:
                raise ValueError("record must be object")
            chunk = dict(identity, text=canonical(_transform(record, True)).decode())
        _original(chunk)
        digest = hashlib.sha256(canonical(chunk)).hexdigest()
        if payload["raw_chunk_sha256"] != digest:
            raise RepresentationError("compact_integrity_failure", "digest mismatch")
        return chunk
    except RepresentationError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise RepresentationError("compact_payload_failure", str(exc)) from exc


def decode_serialized(data):
    """Strict transport boundary: reject duplicate keys before object construction."""
    try:
        if type(data) is bytes:
            data = data.decode("utf-8", errors="strict")
        if type(data) is not str:
            raise ValueError("expected UTF8 bytes or text")
        payload = json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise RepresentationError("compact_payload_failure", str(exc)) from exc
    return decode(payload)
