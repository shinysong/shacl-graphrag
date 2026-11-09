# Augmented manufacturing projection offline parity
9questions×2offlinebackends=18slots; Q7unsupported2. Same seven consumedreal-source nodes, nohistory invented. Existing frozenruntime research/backend-reasoning-review-1/live-001/runtime.py execute(live=False) only SQLStore/RDFStore; no network clients constructed, no evaluatorread. Existingfunction snapshots source/contracts/runtime/triples andplannedslots, preserves load/queryfailures andcleanup. Source+contracthashespreflight bycoordinator. No newDB/LLMcall. No claim liveNeo4j/Neptuneparity fornewqueries.
Motivation: oldQ8askednominal/actual/version butqueryonlyactualempty. RevisedQ8returnsnominalviaexistingcodebooklink plusrowanddictionarypayload. Actual/currentversionnotestablishedinselectedrecords, neverglobalabsence. Q1/Q2locators,Q3settingnumbers additionallyaccessibleinrawpayloads; noanswerfilledfromscorer. Allotherqueries addexplicitpayloadprojection; max8BGPpatterns<=existing12limit. Rawpayloadbytes mustbereported; nofreecontext claim. LaterLLMself/report armsmustgetsamev2sourcebudget. Thisjobonlyofflineexecution, notansweradapter-v2 orpaidlaunch.
Predeclared checks:18slots preserved; expected2unsupportedQ7; forcompletedpairs comparecanonicalbindings, retainallfailures; Q8nominalandpayloadpresent onboth; sameoldprojectedvalues unchangedwherequeriesonlyextended(exceptQ8intentionallychanged); payloadcellprovenancecheckedposthocusingseparaterawsource. Fullnewqueriesbelow. Existingruntime excerpt following describes mainhandling but oldcodefull notprovided; markomissionsunverified.
[
  {
    "id": "Q1",
    "question_type": "Q1",
    "scope": "scalar source value only; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Ax_init_mm>",
        "?v"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ]
    ],
    "project": [
      "?v",
      "?record_payload"
    ],
    "parent_query_hash": "5f4b8de4ce87c8db9610c73cfaa876a560b32aecb99153ad05857dc28e0621f0",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q2",
    "question_type": "Q2",
    "scope": "same-file explicit reference and codebook label; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Adefect>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3ADefect>",
        "?v"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?dictionary_payload"
      ]
    ],
    "project": [
      "?d",
      "?v",
      "?record_payload",
      "?dictionary_payload"
    ],
    "parent_query_hash": "5a83c7e58ee539a6d03a9736609c6d67448fed13d5a0f86a31e700b59113c51e",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q3",
    "question_type": "Q3",
    "scope": "two source operands only; arithmetic not DB-side; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Awelding_setting>",
        "?d1"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A12>",
        "<urn:shacl-study:backend:relation%3Awelding_setting>",
        "?d2"
      ],
      [
        "?d1",
        "<urn:shacl-study:backend:field%3AIdc%20%28A%29>",
        "?v1"
      ],
      [
        "?d2",
        "<urn:shacl-study:backend:field%3AIdc%20%28A%29>",
        "?v2"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?first_record_payload"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A12>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?second_record_payload"
      ],
      [
        "?d1",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?first_dictionary_payload"
      ],
      [
        "?d2",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?second_dictionary_payload"
      ]
    ],
    "project": [
      "?d1",
      "?d2",
      "?v1",
      "?v2",
      "?first_record_payload",
      "?second_record_payload",
      "?first_dictionary_payload",
      "?second_dictionary_payload"
    ],
    "parent_query_hash": "224be2681c881fd30ba36316135b712da137413b8dd75560d615519b5d2bd03c",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q4",
    "question_type": "Q4",
    "scope": "bounded two-row candidates only; filtering/count separate; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "?s",
        "<urn:shacl-study:backend:field%3Ax_init_mm>",
        "?x"
      ],
      [
        "?s",
        "<urn:shacl-study:backend:relation%3Adefect>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3ADefect>",
        "?label"
      ],
      [
        "?s",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?dictionary_payload"
      ]
    ],
    "project": [
      "?s",
      "?x",
      "?d",
      "?label",
      "?record_payload",
      "?dictionary_payload"
    ],
    "parent_query_hash": "60b2ccfd998b933dfb69e9b3c6893d50736f270c8436228e6885fec4a40ef623",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q5",
    "question_type": "Q5",
    "scope": "raw values; measured-versus-nominal prose not evaluated; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Ax_init_mm>",
        "?mm"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Asample_init>",
        "?sample"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Awelding_setting>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3AIdc%20%28A%29>",
        "?nominal"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?dictionary_payload"
      ]
    ],
    "project": [
      "?mm",
      "?sample",
      "?nominal",
      "?record_payload",
      "?dictionary_payload"
    ],
    "parent_query_hash": "dc9ec8776f9cf44e8103c7f5250692642827ca9b185d8143049fd47bae61a8b3",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q6",
    "question_type": "Q6",
    "scope": "declared source identity only; policy not inferred; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Adefect>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Acoupon>",
        "?same"
      ],
      [
        "<urn:shacl-study:backend:PP7%3Adefect_code%3A4>",
        "<urn:shacl-study:backend:field%3Acoupon>",
        "?other"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?dictionary_payload"
      ],
      [
        "<urn:shacl-study:backend:PP7%3Adefect_code%3A4>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?other_dictionary_payload"
      ]
    ],
    "project": [
      "?d",
      "?same",
      "?other",
      "?record_payload",
      "?dictionary_payload",
      "?other_dictionary_payload"
    ],
    "parent_query_hash": "b8736c9750823b9e9503f07fa0603e7ffe484feaf90e9d7d6ea0c3c85c30e6f0",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q7",
    "question_type": "Q7",
    "scope": "synthetic history excluded from real-source pass",
    "unsupported": "No real version history in selected source; do not invent it",
    "parent_query_hash": "911ebe76067592325ca8ab073919f707fe797f3d46a32eb281b208f74748cfeb",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q8",
    "question_type": "Q8",
    "scope": "Nominal setting and selected record payloads; actual measured current and version not established in these records, not global absence; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Awelding_setting>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3AIdc%20%28A%29>",
        "?nominal"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?dictionary_payload"
      ]
    ],
    "project": [
      "?d",
      "?nominal",
      "?record_payload",
      "?dictionary_payload"
    ],
    "parent_query_hash": "dd4bc52e6d324d04ceffb931a8f15f343c2d1dcaad084bc4a97de6f31746fc4b",
    "projection_revision": "source-payload-provenance-v2"
  },
  {
    "id": "Q9",
    "question_type": "Q9",
    "scope": "authored-draft supporting values only; no prose classification; source locators and codebook fields available in explicit payload projection; downstream interpretation remains declared policy",
    "patterns": [
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Adefect>",
        "?d"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3ADefect>",
        "?label"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:relation%3Awelding_setting>",
        "?w"
      ],
      [
        "?w",
        "<urn:shacl-study:backend:field%3AIdc%20%28A%29>",
        "?nominal"
      ],
      [
        "<urn:shacl-study:backend:PP6%3A2>",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?record_payload"
      ],
      [
        "?d",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?defect_dictionary_payload"
      ],
      [
        "?w",
        "<urn:shacl-study:backend:field%3Apayload>",
        "?setting_dictionary_payload"
      ]
    ],
    "project": [
      "?label",
      "?nominal",
      "?record_payload",
      "?defect_dictionary_payload",
      "?setting_dictionary_payload"
    ],
    "parent_query_hash": "ce944b74333158d740a31d3b89c9664ee9955feaa9812b09f7f841f9c64b72d3",
    "projection_revision": "source-payload-provenance-v2"
  }
]

Runtime execute excerpt:
source_path, contracts_path, output, live=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path(source_path).read_text());contracts=json.loads(Path(contracts_path).read_text())
    (output/'source.json').write_text(canonical(source)+'\n')
    (output/'contracts.json').write_text(canonical(contracts)+'\n')
    (output/'runtime.py').write_bytes(Path(__file__).read_bytes())
    triples=triples_from_source(source)
    (output/'triples.json').write_text(canonical(triples)+'\n')
    # Runtime never reads evaluator reference files.
    names=['sqlite_python','rdflib_offline']+(['neo4j_cypher','neptune_sparql'] if live else [])
    plan=[{'backend':name,'case_id':q['id'],'status':'planned'} for name in names for q in contracts]
    (output/'plan.json').write_text(canonical(plan)+'\n')
    namespace='backend-'+output.name
    constructors=[SQLStore,RDFStore]+([lambda:NeoStore(namespace),lambda:NeptuneStore(namespace)] if live else [])
    cleanup=[]
    with (output/'results.jsonl').open('a') as results:
        for name,constructor in zip(names,constructors,strict=True):
            try:
                store=None;load_error=None;t=time.perf_counter()
                try:
                    store=constructor();store.load(triples)
                except Exception as exc:
                    load_error=type(exc).__name__+': '+str(exc)
                load_ms=(time.perf_counter()-t)*1000
                for q in contracts:
                    row={'backend':name,'case_id':q['id'],'question_type':q['question_type'],'scope':q['scope'],'source_hash':digest(source),'contract_hash':digest(q),'load_ms_shared':load_ms}
                    t=time.perf_counter()
                    try:
                        if load_error: raise RuntimeError(load_error)
                        if q.get('unsupported'):
                            row.update(status='unsupported',reason=q['unsupported'])
                        else:
                            bindings=store.query(q['patterns'],q['project'])
                            row.update(status='completed',bindings=bindings,binding_sha256=digest(bindings))
                    except Exception as exc:
                        row.update(status='dependency_not_run' if load_error else 'query_failure',error=type(exc).__name__+': '+str(exc))
                    row['elapsed_ms']=(time.perf_counter()-t)*1000
                    results.write(canonical(row)+'\n');results.flush()
            finally:
                if store:
                    try:cleanup.append({'backend':name,'status':'completed','receipt':store.cleanup()})
                    except Exception as exc:cleanup.append({'backend':name,'status':'failed','error':str(exc)})
                else:cleanup.append({'backend':name,'status':'not_constructed','error':load_error})
                (output/'cleanup.json').write_text(canonical(cleanup)+'\n')
    (output/'cleanup.json').write_text(canonical(cleanup)+'\n')
    return plan

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--contracts',required=True);p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    execute(a.source,a.contracts,a.output,a.live)
