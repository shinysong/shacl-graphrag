# Question input availability diagnostic
Manual question paths, not automatic question parsing or semantic correctness. Compare36historicalbackend slots and18newoffline slots without replacing prior results. Source truth and complete answers not certified; missing/explicitnull/empty distinguished. Same-valuedwrongsource intentionallypasses presence-only diagnostic. No source lookups or gold repair. Q7 retained unsupported. Three direct tests pass; rawdataomitted unverified.

```python
"""Inspect declared input obligations, never infer truth or repair answers."""
from scripts.manufacturing_answer_adapter import decode


def inspect_path(row, path):
    current = row
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return 'missing'
    if current is None:
        return 'explicit_null'
    if isinstance(current, (str, list, dict)) and not current:
        return 'empty'
    return 'present'


def coverage(saved, contract):
    result = {'backend': saved['backend'], 'question_id': saved['case_id'],
              'upstream_status': saved['status'], 'status': 'not_evaluated',
              'obligations': [], 'claim_scope': 'input availability under authored paths, not answer correctness'}
    if saved['status'] != 'completed':
        result['status'] = 'unsupported' if saved['status'] == 'unsupported' else 'upstream_failure'
        return result
    try:
        rows = [{k: decode(v) for k, v in row.items()} for row in saved['bindings']]
        for obligation in contract['obligations']:
            observations = [[inspect_path(row, p) for p in obligation['paths']] for row in rows]
            present = bool(rows) and all(all(s == 'present' for s in states) for states in observations)
            result['obligations'].append({'id': obligation['id'], 'label': obligation['label'],
                                          'input_available': present, 'observations': observations})
        result['status'] = 'inspected'
        result['available_count'] = sum(o['input_available'] for o in result['obligations'])
        result['declared_count'] = len(result['obligations'])
        # No all-complete flag: path presence does not establish scope, identity, or semantic correctness.
        return result
    except (ValueError, TypeError, KeyError) as exc:
        result['status'] = 'input_error'
        result['error'] = type(exc).__name__ + ':' + str(exc)
        return result

```

```python
import json
from rdflib import Literal
from scripts.manufacturing_obligation_coverage import coverage, inspect_path


def test_missing_null_empty_and_zero_are_distinct():
    row={'null':None,'empty':'','zero':0,'list':[4]}
    assert [inspect_path(row,[k]) for k in ('absent','null','empty','zero')]==['missing','explicit_null','empty','present']
    assert inspect_path(row,['list',1])=='missing'


def test_empty_binding_and_one_missing_row_do_not_pass():
    c={'obligations':[{'id':'value','label':'requested scalar','paths':[['?v']]}]}
    s={'backend':'test','case_id':'Q1','status':'completed','bindings':[]}
    assert coverage(s,c)['available_count']==0
    s['bindings']=[{'?v':Literal(json.dumps(0)).n3()},{}]
    assert coverage(s,c)['available_count']==0
    s['bindings']=s['bindings'][:1]
    assert coverage(s,c)['available_count']==1


def test_same_valued_wrong_source_is_not_detected_by_presence():
    c={'obligations':[{'id':'location','label':'source','paths':[['?payload','archive_path']]}]}
    s={'backend':'test','case_id':'Q6','status':'completed',
       'bindings':[{'?payload':Literal(json.dumps({'archive_path':'wrong.xlsx'})).n3()}]}
    assert coverage(s,c)['available_count']==1  # Deliberate known limit, not a semantic check.

```

```json
{
  "id": "question-input-availability-v1",
  "origin": "manual decomposition of existing question text and declared query interface; not automatic NL extraction",
  "limits": [
    "Availability only; not final-answer completeness, external truth, source applicability or closed-world completeness",
    "Absent paths do not locate loss upstream; source vs retrieval diagnosed separately",
    "Q7 actual history unsupported; do not invent from earlier synthetic history"
  ],
  "questions": {
    "Q1": {
      "obligations": [
        {
          "id": "value",
          "label": "requested scalar",
          "paths": [
            [
              "?v"
            ]
          ]
        },
        {
          "id": "location",
          "label": "record cell locator",
          "paths": [
            [
              "?record_payload",
              "archive_path"
            ],
            [
              "?record_payload",
              "sheet"
            ],
            [
              "?record_payload",
              "sha256"
            ],
            [
              "?record_payload",
              "field_cells",
              "x_init_mm"
            ]
          ]
        }
      ]
    },
    "Q2": {
      "obligations": [
        {
          "id": "label",
          "label": "codebook label",
          "paths": [
            [
              "?v"
            ]
          ]
        },
        {
          "id": "relation",
          "label": "dictionary identity",
          "paths": [
            [
              "?d"
            ]
          ]
        },
        {
          "id": "record_location",
          "label": "record defect cell",
          "paths": [
            [
              "?record_payload",
              "archive_path"
            ],
            [
              "?record_payload",
              "sheet"
            ],
            [
              "?record_payload",
              "sha256"
            ],
            [
              "?record_payload",
              "field_cells",
              "defect"
            ]
          ]
        },
        {
          "id": "dictionary_location",
          "label": "dictionary source and cells",
          "paths": [
            [
              "?dictionary_payload",
              "archive_path"
            ],
            [
              "?dictionary_payload",
              "sheet"
            ],
            [
              "?dictionary_payload",
              "sha256"
            ],
            [
              "?dictionary_payload",
              "cells"
            ]
          ]
        }
      ]
    },
    "Q3": {
      "obligations": [
        {
          "id": "first_setting",
          "label": "first setting number",
          "paths": [
            [
              "?first_record_payload",
              "values",
              "welding_setting"
            ]
          ]
        },
        {
          "id": "second_setting",
          "label": "second setting number",
          "paths": [
            [
              "?second_record_payload",
              "values",
              "welding_setting"
            ]
          ]
        },
        {
          "id": "first_nominal",
          "label": "first nominal operand",
          "paths": [
            [
              "?v1"
            ]
          ]
        },
        {
          "id": "second_nominal",
          "label": "second nominal operand",
          "paths": [
            [
              "?v2"
            ]
          ]
        },
        {
          "id": "difference_inputs",
          "label": "difference operands available; arithmetic not checked",
          "paths": [
            [
              "?v1"
            ],
            [
              "?v2"
            ]
          ]
        }
      ]
    },
    "Q4": {
      "obligations": [
        {
          "id": "identities",
          "label": "candidate identities; universe coverage not checked",
          "paths": [
            [
              "?s"
            ]
          ]
        },
        {
          "id": "filter_inputs",
          "label": "filter operands; predicate not executed",
          "paths": [
            [
              "?x"
            ],
            [
              "?label"
            ]
          ]
        }
      ]
    },
    "Q5": {
      "obligations": [
        {
          "id": "position",
          "label": "position scalar",
          "paths": [
            [
              "?mm"
            ]
          ]
        },
        {
          "id": "index",
          "label": "sample scalar",
          "paths": [
            [
              "?sample"
            ]
          ]
        },
        {
          "id": "nominal",
          "label": "nominal scalar",
          "paths": [
            [
              "?nominal"
            ]
          ]
        },
        {
          "id": "role_context",
          "label": "source headers for declared interpretation",
          "paths": [
            [
              "?record_payload",
              "header_rows"
            ],
            [
              "?dictionary_payload",
              "header_rows"
            ]
          ]
        },
        {
          "id": "measured",
          "label": "actual measured observation; absence remains local",
          "paths": [
            [
              "?actual_current"
            ]
          ]
        }
      ]
    },
    "Q6": {
      "obligations": [
        {
          "id": "linked",
          "label": "linked dictionary identity",
          "paths": [
            [
              "?d"
            ]
          ]
        },
        {
          "id": "sources",
          "label": "source scopes for declared applicability policy",
          "paths": [
            [
              "?same"
            ],
            [
              "?other"
            ]
          ]
        },
        {
          "id": "source_locations",
          "label": "both dictionary source locations",
          "paths": [
            [
              "?dictionary_payload",
              "archive_path"
            ],
            [
              "?other_dictionary_payload",
              "archive_path"
            ]
          ]
        }
      ]
    },
    "Q7": {
      "obligations": [
        {
          "id": "history",
          "label": "effective document history",
          "paths": [
            [
              "?history"
            ]
          ]
        },
        {
          "id": "version",
          "label": "applicable version",
          "paths": [
            [
              "?version"
            ]
          ]
        }
      ]
    },
    "Q8": {
      "obligations": [
        {
          "id": "nominal",
          "label": "nominal scalar",
          "paths": [
            [
              "?nominal"
            ]
          ]
        },
        {
          "id": "nominal_source",
          "label": "nominal source context",
          "paths": [
            [
              "?dictionary_payload",
              "archive_path"
            ],
            [
              "?dictionary_payload",
              "header_rows"
            ]
          ]
        },
        {
          "id": "actual",
          "label": "actual observation not in projected evidence",
          "paths": [
            [
              "?actual_current"
            ]
          ]
        },
        {
          "id": "version",
          "label": "applicable version not in projected evidence",
          "paths": [
            [
              "?version"
            ]
          ]
        }
      ]
    },
    "Q9": {
      "obligations": [
        {
          "id": "label",
          "label": "source label for draft comparison",
          "paths": [
            [
              "?label"
            ]
          ]
        },
        {
          "id": "nominal",
          "label": "nominal scalar",
          "paths": [
            [
              "?nominal"
            ]
          ]
        },
        {
          "id": "review_locations",
          "label": "source locations for human review",
          "paths": [
            [
              "?record_payload",
              "archive_path"
            ],
            [
              "?defect_dictionary_payload",
              "archive_path"
            ],
            [
              "?setting_dictionary_payload",
              "archive_path"
            ]
          ]
        },
        {
          "id": "actual",
          "label": "actual measured observation not established",
          "paths": [
            [
              "?actual_current"
            ]
          ]
        }
      ]
    }
  }
}
```