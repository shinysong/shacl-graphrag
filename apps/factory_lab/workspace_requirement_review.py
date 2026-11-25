"""Record model-declared requirement resolution, without judging semantic truth."""
from copy import deepcopy

CAPABILITY_PLANNING = """
When asked what questions can be answered or what pending reviews affect, inspect
both the advertised business-query descriptors and relevant saved review entries.
Overview counts alone do not answer a capability or review-impact question. Follow
catalog pages when needed within the existing budget; explicitly preserve any
uninspected remainder. Do not execute a business query merely to list its capability.
Use observed field/relation identifiers and policy paragraph locators to explain
concrete examples of questions needing review. A policy topic or proposed relation
suggests a possible review concern, not a verified dependency or automatic blocker.
Distinguish an advertised recorded-value lookup from a policy/eligibility decision.
Do not infer that every pending entry blocks every query. If no explicit dependency
or applicability evidence is available, say the effect is unverified and identify
what needs review instead of inventing one. Keep unanswered parts in unresolved.
"""

GUIDANCE = '''
Write for the user in their language; explain observations rather than listing
internal JSON keys. Keep literal source column names, but explain system metadata
in ordinary language: saved sample versus whole-source count, pending review,
and currently advertised approved queries. Do not generalize a paginated result
to unseen items. Exploration business_authorization=false means THIS RESULT does
not grant business approval; it is not a global access/permission denial. Determine
available business queries from the separate query catalog and execution results.
An empty approved-query catalog means no such query is advertised, not absent data
or a ban on source exploration. A metadata flag is not an access-control decision.
The input unresolved list includes earlier planning concerns, not necessarily
still-unanswered requirements. Reconcile those concerns against executed evidence.
You may add an optional resolved_requirements array to the final answer object.
Each item must have exactly requirement (an exact earlier unresolved string),
citations (nonempty successful evidence IDs also cited in the final answer), and
explanation (why that requirement is answered). Omitted entries remain unresolved.
Only claim resolution when the cited evidence answers the actual requirement;
a successful tool call alone does not resolve a question. Preserve unsupported
requests. Do not invent new requirements that the user did not ask for.
This is your interpretation, not a server-verified factual judgment.
'''


def reconcile(previous, final, valid):
    resolutions = final.get('resolved_requirements', [])
    if not isinstance(resolutions, list) or len(resolutions) > 64:
        raise ValueError('Invalid requirement resolution records')
    resolved = set()
    for item in resolutions:
        if not isinstance(item, dict) or set(item) != {'requirement', 'citations', 'explanation'}:
            raise ValueError('Invalid requirement resolution record')
        requirement = item['requirement']; citations = item['citations']
        if (not isinstance(requirement, str) or requirement not in previous or requirement in resolved
                or requirement in final['unresolved']
                or not isinstance(citations, list) or not 1 <= len(citations) <= 64
                or any(not isinstance(c, str) or c not in valid or c not in final['citations'] for c in citations)
                or not isinstance(item['explanation'], str) or not 1 <= len(item['explanation']) <= 2000):
            raise ValueError('Unbound requirement resolution')
        resolved.add(requirement)
    return {
        'planning_unresolved': deepcopy(previous),
        'requirement_resolutions': deepcopy(resolutions),
        'resolution_authority': 'model_interpretation_not_verified_truth',
        'unresolved': list(dict.fromkeys([s for s in previous if s not in resolved] + final['unresolved'])),
    }
