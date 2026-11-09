"""Shared literal-anchor candidate ordering; no source lookup or evaluation inputs."""
import copy

STATUSES = {'resolved_unique', 'locator_unsupported', 'source_not_found',
            'source_ambiguous', 'source_invalid'}


def inject_anchor(base, locator):
    """Preserve upstream status; return original ranking and displacement audit.

    Caller must supply an authentic resolver result and validate source identity.
    This function validates the ordering contract, not the truth of the locator.
    """
    if not isinstance(base, dict) or not isinstance(locator, dict):
        raise ValueError('base and locator must be objects')
    status = base.get('upstream_status')
    ids = base.get('ordered_candidate_ids')
    if (not isinstance(status, str) or not status or not isinstance(ids, list)
            or len(ids) > 8 or any(not isinstance(x, str) or not x for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('invalid base ranking')
    state = locator.get('status')
    anchors = locator.get('candidate_chunk_ids')
    if (state not in STATUSES or not isinstance(anchors, list)
            or any(not isinstance(x, str) or not x for x in anchors)
            or len(set(anchors)) != len(anchors)):
        raise ValueError('invalid locator result')
    if state == 'resolved_unique' and len(anchors) != 1:
        raise ValueError('unique locator requires one candidate')
    if state == 'source_ambiguous' and len(anchors) < 2:
        raise ValueError('ambiguous locator requires multiple candidates')
    if state in {'locator_unsupported', 'source_not_found', 'source_invalid'} and anchors:
        raise ValueError('nonresolved locator must have no candidates')
    # No rescue of an unsuccessful upstream retrieval: retain failure and ranking.
    applied = state == 'resolved_unique' and status == 'ok'
    ordered = list(dict.fromkeys(anchors + ids))[:8] if applied else list(ids)
    result = copy.deepcopy(base)
    result.update(ordered_candidate_ids=ordered,
                  anchor_audit=dict(locator_status=state, applied=applied,
                      original_candidate_ids=list(ids),
                      anchor_candidate_ids=list(anchors),
                      displaced_candidate_ids=[x for x in ids if x not in ordered],
                      added_candidate_ids=[x for x in ordered if x not in ids],
                      reason=('unique_anchor_promoted' if applied else
                              'upstream_failure_preserved' if status != 'ok' else
                              'locator_not_unique')))
    return result
