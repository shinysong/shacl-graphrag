# Supplemental code and questions
Underlying sources, upstream builder and old19questions omitted/unverified. See the supplied report packet for scope.

## Static presentation builder
```python
"""Add scope/navigation to the existing saved-result demo; no DB or API calls."""
import runpy
import tempfile
from pathlib import Path

OUT = Path('docs/experiments/seminar/manufacturing-trace.html')
UPSTREAM = Path('research/manufacturing-model-change-1/import-demo-001/build.py')
OLD = '<p>같은 값을 조회해도 질문에 필요한 근거를 모두 전달한 것은 아닙니다. 작업표와 코드북의 원문 셀, 조회 결과, 입력 항목 점검을 연결해 봅니다. 제조 사례가 중심이며, 실제 버전 변경은 SBOM 보조 사례에서 따로 확인합니다.</p>'
NEW = '''<section id="research-scope" class="card">
<h2>독립된 두 제조 자료의 검토</h2>
<p>용접 자료에서는 작업표·코드북·측정값 해석을, 공개 MachineTool 모델에서는 타입 관계와 실제 버전 변경을 점검했습니다. 두 자료가 같은 설비를 가리킨다는 연결은 검증하지 않았습니다. 하나의 현장 시스템을 끝까지 검증한 결과가 아닙니다.</p>
<p>이 화면은 저장된 개발 결과를 재생합니다. SHACL의 추가 답변 개선 효과, 사람의 검토 시간, DB 성능 우열은 확인되지 않았습니다. SBOM은 별도의 보조 사례입니다.</p>
<nav aria-label="연구 결과 탐색"><a href="#question-title">용접 근거</a> · <a href="#hierarchy-demo">모델·추론·변경</a> · <a href="#import-context-demo">외부 정의 추가</a> · <a href="measurement-review.html">실제 LLM 답변</a> · <a href="../../journal/2026-11-07-manufacturing-research-map/">질문·구현·기여 정리</a></nav>
</section>'''


def build():
    upstream = runpy.run_path(str(UPSTREAM))
    with tempfile.TemporaryDirectory(dir='_workspace') as directory:
        temporary = Path(directory) / 'base.html'
        upstream['build'](temporary)
        source = temporary.read_text()
    if source.count(OLD) != 1 or 'id="research-scope"' in source:
        raise ValueError('unexpected_upstream_presentation')
    OUT.write_text(source.replace(OLD, NEW))
    return {'scope_section': 1, 'upstream_result_data_unchanged': True,
            'db_or_api_called': False}


if __name__ == '__main__':
    print(build())

```

## New explanatory questions only
[
  {
    "id": "W-Q8a",
    "question": "실제 HDF 파일까지 제공했을 때 PP6 2행의 명목 Idc, 전류 채널 유무, 검증된 결함 구간 평균, 적용 문서 버전 중 무엇을 말할 수 있나요?",
    "domain": "manufacturing_measurement",
    "artifact": "research/manufacturing-measurement-1/answer-001",
    "measured_here": "One consumed question ×6models×draft/self/SHACL=18completed; fourfields agree allarms; no incremental improvement opportunity",
    "not_measured": "Source packet manually assembled; alignment/calibration/physicaltruth and human utility not validated",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  },
  {
    "id": "T1",
    "question": "MachineTool StateMachineType(i=24)의 상위 타입은 무엇인가요? 직접 관계와 추론 경로를 구분해주세요.",
    "domain": "manufacturing_published_schema",
    "artifact": "research/manufacturing-model-change-1/subtype-live-001",
    "measured_here": "248typed questions×4adapters=992slots;868completed124selectedn10sancestoradapterunsupported",
    "not_measured": "No full OPC declaration/OWL semantics or engine performance",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  },
  {
    "id": "T2",
    "question": "MachineTool StateMachineType(i=24)에 직접 또는 간접적으로 속하는 모델 객체는 무엇인가요?",
    "domain": "manufacturing_published_schema",
    "artifact": "research/manufacturing-model-change-1/subtype-live-001",
    "measured_here": "Same consumed hierarchy study asT1, not independent trials. Example direct0 vsclosure7 model objects",
    "not_measured": "Not observed physical equipment; not universal n10s capability limit",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  },
  {
    "id": "T3",
    "question": "선택한 IA 정의를 추가하면 MachineTool i=117 모델 객체의 타입 집합과 근거 경로가 어떻게 바뀌나요?",
    "domain": "manufacturing_published_schema",
    "artifact": "research/manufacturing-model-change-1/object-type-context-001",
    "measured_here": "Posthoc all300originalobjects1200slots;4questions changed;600PythonOWLpairs agree",
    "not_measured": "Added source access; no strongerreasoner or newactualDB measurement",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  },
  {
    "id": "M1",
    "question": "ObligationType(i=1002)의 기존 정의와 답의 근거가 그대로여도 새 객체가 추가되면 어느 조회를 다시 확인해야 하나요?",
    "domain": "manufacturing_published_schema",
    "artifact": "research/manufacturing-model-change-1/query-footprint-001",
    "measured_here": "124membershipqueries1changed;positivepath-only misses1; adjacencybucketflags1 undercomplete snapshots",
    "not_measured": "No minimaldependency guarantee or measuredhuman maintenance effort",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  },
  {
    "id": "M2",
    "question": "MachineTool 파일에 명시된 필수·선택 모델링 규칙은 어디에 있고, 지금 구현이 그 규칙까지 검사하나요?",
    "domain": "manufacturing_published_schema",
    "artifact": "research/manufacturing-model-change-1/modelling-rules-002",
    "measured_here": "Four originalXMLinventoryslotscomplete;371/76/407/76 explicitlytagged nodes; actualconformance notrun",
    "not_measured": "No inheriteddeclaration expansion, liveinstance validation or site compliance",
    "source_basis": "Consumed development sources; question wording is posthoc explanatory index, not frozen experimental prompt"
  }
]
## Executed query excerpts
{
  "source_sha256": "2cb47c38664e92bba2107d41d419de1c48f9925e9b626f01e8011a957e5a99d2",
  "extraction": "Exact AST source spans of executed live.py; nonexecutable excerpts, transport/resource configuration intentionally excluded. No claim of complete reproduction package. Existing run cutoff expired; no resource calls authorized by reading this.",
  "excerpts": {
    "triples": "def triples(p,materialized):\n g=Graph()\n for a,b in p['edges']:g.add((h.u(a),RDFS.subClassOf,h.u(b)))\n for a,b in p['types']:g.add((h.u(a),RDF.type,h.u(b)))\n if materialized:\n  for c in p['allclasses']:g.add((h.u(c),RDF.type,OWL.Class))\n  DeductiveClosure(OWLRL_Semantics,axiomatic_triples=False,datatype_axioms=False).expand(g)\n return sorted({(h.u(a).n3(),RDFS.subClassOf.n3(),h.u(b).n3()) for a in p['allclasses'] for b in p['allclasses'] if a!=b and (h.u(a),RDFS.subClassOf,h.u(b)) in g}|{(h.u(o).n3(),RDF.type.n3(),h.u(c).n3()) for o in p['objects'] for c in p['allclasses'] if (h.u(o),RDF.type,h.u(c)) in g})",
    "Neo.query": " def query(self,q,n10s=False):\n  if n10s:\n   if q['kind']!='model_object_members':raise NotImplementedError('ancestor_not_in_selected_n10s_adapter')\n   statement='MATCH(c:SubtypeClass {run:$run,id:$target}) CALL n10s.inference.nodesInCategory(c,{inCatRel:\"TYPEOF\",subCatRel:\"SUBTYPE\"}) YIELD node WHERE node:SubtypeObject AND node.run=$run RETURN DISTINCT node.id AS id'\n  elif q['kind']=='ancestors':statement='MATCH(s:SubtypeClass {run:$run,id:$target})-[:SUBTYPE*1..]->(n:SubtypeClass) WHERE n.run=$run AND n.id<>$target RETURN DISTINCT n.id AS id'\n  else:statement='MATCH(n:SubtypeObject {run:$run})-[:TYPEOF]->(:SubtypeClass)-[:SUBTYPE*0..]->(c:SubtypeClass {run:$run,id:$target}) RETURN DISTINCT n.id AS id'\n  return sorted(r['id'] for r in self.request(statement,{'target':q['target']}))",
    "sparql": "def sparql(store,q,p,materialized=False):\n target=h.u(q['target']).n3();sc=RDFS.subClassOf.n3();typ=RDF.type.n3()\n if q['kind']=='ancestors':pattern=target+' '+sc+('' if materialized else '+')+' ?x'\n else:pattern='?x '+typ+('' if materialized else '/'+sc+'*')+' '+target\n query='SELECT DISTINCT ?x WHERE {GRAPH '+store.graph+' {'+pattern+'}}'\n result=store.request(query);decode={str(h.u(k)):k for k in p['allclasses']|p['objects']}\n return sorted({decode[r['x']['value']] for r in result['results']['bindings'] if r['x']['type']=='uri'})"
  },
  "prelaunch_binding": {
    "at": "2026-11-07T17:11:22.646036+00:00",
    "source_hash_matches_prelaunch_v4": true,
    "prior_freeze_is_earlier_unexecuted_version": true
  }
}

## Prior source bound inventory summary
{
  "audit": "Coordinator separate raw XML parser, no runtime module import, no repair. Not independent human review.",
  "source_slots": 4,
  "rows": [
    {
      "source_sha256": "849b29895d096867856642c777b1f6b1c9854c9932354b10a45089d3af7f6e74",
      "marked_nodes": 371,
      "all_rule_sets_equal": true
    },
    {
      "source_sha256": "8524927d2d75cbf15c10711cd8a463820adaf24a259d4c8a656321c55186f20b",
      "marked_nodes": 76,
      "all_rule_sets_equal": true
    },
    {
      "source_sha256": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "marked_nodes": 407,
      "all_rule_sets_equal": true
    },
    {
      "source_sha256": "2a198ed96604eaf473d1ebfb4b29d745a7af8eed74c0f96ab1ac5f1fb71e4de9",
      "marked_nodes": 76,
      "all_rule_sets_equal": true
    }
  ],
  "total_marked_node_occurrences": 930,
  "frozen_files_unchanged": true
}
