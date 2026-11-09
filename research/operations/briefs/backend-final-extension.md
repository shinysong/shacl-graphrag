# Final saved-results extension review
Priorqueryscope/finitecode separatelyreviewed andexecuted. Observed640/640slots,320pairsagree;declaredqueryper16010flags8mismatch2matching0miss;wrongquery10flags0mismatch10matching8miss. Fiveoracleknowncasespassed;12288/12288finiteenumerationstates,3824exactdependencygroups,zero differentanswerwithinidenticaldependencygroup. Boundedsoftwareproperty,nominimality/generalproof/QAclaim. Existingreportreviewcompletedbeforethisadditiveparagraph. NewHTMLadds2querypoliciesto3familypolicies,160savedoutputs800reportpairs,posthocrefdisplayonly(noevalgoldruntime). Buildernowenforcesall displayed/originalpairedfields, bindsorigin/originalanswer/status againstrow, fullplannedcoverage;reviewpriorwarningaddressed. OriginalHTMLversion and226filesnapshotarchivedprivately; nohistoryoverwrite. GeneratedJSONomitted,source/templateincluded. Browser160selectorcombinations×5=800cardcheckplanned plusmobile/dark. NoDB/LLM/networkclient/push. Omittedrawfilesunverified. Reviewappendixclaimlimitsandchangedpresentationonly, notpreviouswholeexperiments. Keepfindingsconcise.

REPORT ADDITION
### 조회 대상과 연결 경로의 확인 범위

질문 유형만 구분한 검사 다음에는 실제 조회 대상과 연결된 사실·규칙 경로로 확인 범위를 좁혔다. 타입 질문은 목표 타입으로 이어지는 사실과 계층 경로를, 관계 질문은 시작 노드와 목표 관계에 연결된 사실·경로를 사용했다. 현재 자료와 사용 자료에 같은 계산을 적용했다. 검사기는 그 결과로 제공된 해시만 받았다.

| 추가 확인 범위 | 검토 경고 | 불일치 결과에 경고 | 일치 결과에도 경고 | 불일치인데 경고 없음 |
|---|---:|---:|---:|---:|
| 선언한 조회 대상·경로 | 10 | 8 | 2 | 0 |
| 다른 조회를 연결한 대조 조건 | 10 | 0 | 10 | 8 |

각 행은 같은 160개 저장 결과를 다시 검사한 것이다. 640개 검사 슬롯이 완료됐고 Python·SHACL 보고서 320쌍이 같았다. 일치 결과에도 남은 경고 2개는 대체 경로가 남아 답 집합은 같지만 근거 경로가 바뀐 경우였다. 질문 유형 수준의 경고 12개에서 조회 수준의 2개로 줄었지만, 잘못된 조회를 연결한 대조 조건은 불일치 결과 8개를 모두 놓쳤다.

이 계산에는 전체가 제공된 작은 원천 스냅샷과 명시적인 조회 계약을 사용했다. 외부 원천의 누락을 찾아내거나 자연어 질문에서 계약을 추출한 성과가 아니다. RDFS 전체 규칙 대신 이번 타입·관계 계층 규칙만 다뤘다. 자료를 좁혀 계산하는 전처리의 효과이며 SHACL만의 장점으로 해석하지 않는다. 향후 LLM 비교에서는 이 전처리 정보의 접근 범위와 비용도 조건별로 같게 맞춰야 한다.

별도 소프트웨어 점검에서는 기호 3개의 가능한 방향 그래프와 제한된 사실 배치를 모두 열거했다. 타입 8,192개와 관계 4,096개를 합친 12,288개 상태를 별도의 행렬 전이 폐쇄 계산과 대조했다. 같은 의존성 내용이 서로 다른 조회 답을 낸 반례는 3,824개 의존성 묶음에서 없었다. 이는 정해진 작은 상태 공간의 조건부 점검이며 최소 확인 범위나 임의의 RDF·OWL 그래프에 대한 일반 증명이 아니다. 과거 연구의 12,288개 자료와도 별개다.



FILE scripts/build_backend_replay.py
"""Build a self-contained presentation of saved backend results (posthoc only)."""
import hashlib
import json
from pathlib import Path

BASE = Path('research/backend-reasoning-review-1')
TARGET = Path('docs/experiments/seminar/backend-review.html')
TEMPLATE = Path('research/backend-reasoning-review-1/presentation-template.html')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def build():
    source = BASE / 'updates-live-001'
    rows = read_rows(source / 'results.jsonl')
    evaluation = json.loads((source / 'evaluation.json').read_text())
    ref = {(x['event'], x['arm'], x['query_id']): x['matches_current_reference'] for x in evaluation['checks']}
    reports = read_rows(BASE / 'advisory-scope-001/results.jsonl') + read_rows(BASE / 'advisory-query-scope-001/results.jsonl')
    lookup = {(r['row_index'], r['policy'], r['checker']): r for r in reports}
    cards = []
    for i, row in enumerate(rows):
        paired = {}
        for policy in ('global', 'declared_family', 'swapped_family_control', 'declared_query', 'swapped_query_control'):
            a, b = [lookup[(i, policy, c)] for c in ('python', 'shacl')]
            if a['status'] != 'completed' or b['status'] != 'completed' or a['codes'] != b['codes']:
                raise ValueError('Presentation requires explicit handling of checker failures/disagreement')
            fields = ('review_requested', 'family', 'metadata', 'origin', 'original_answer', 'original_status', 'answer_changed')
            if any(a[field] != b[field] for field in fields):
                raise ValueError('Displayed report fields or original output disagree')
            if a['original_answer'] != row['answer'] or a['original_status'] != row['status'] or a['answer_changed']:
                raise ValueError('Report is not bound to its original output')
            if a['origin'] != {k: row[k] for k in ('event', 'arm', 'query_id')}:
                raise ValueError('Report origin disagrees with saved output')
            paired[policy] = {'review': a['review_requested'], 'codes': a['codes'], 'family': a['family'], 'metadata': a['metadata']}
        cards.append({k: row[k] for k in ('event', 'arm', 'query_id', 'answer', 'status')} | {
            'matches_declared_reference': ref[(row['event'], row['arm'], row['query_id'])], 'reports': paired})
    plan = json.loads((source / 'plan.json').read_text())
    key = lambda x: (x['event'], x['arm'], x['query_id'])
    if (len(cards) != len(plan) or len({key(x) for x in cards}) != len(cards)
            or {key(x) for x in cards} != {key(x) for x in plan}):
        raise ValueError('Incomplete or duplicate presentation coverage')
    inputs = [source / 'results.jsonl', source / 'evaluation.json', BASE / 'advisory-scope-001/results.jsonl', BASE / 'advisory-query-scope-001/results.jsonl']
    payload = {'cards': cards, 'events': list(dict.fromkeys(r['event'] for r in rows)),
               'queries': list(dict.fromkeys(r['query_id'] for r in rows)),
               'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    template = TEMPLATE.read_text()
    if template.count('__SAVED_EVIDENCE__') != 1:
        raise ValueError('Expected one saved-evidence placeholder')
    TARGET.write_text(template.replace('__SAVED_EVIDENCE__', encoded))
    print(json.dumps({'path': str(TARGET), 'saved_outputs': len(cards), 'report_pairs': len(cards)*5, 'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()

FILE research/backend-reasoning-review-1/presentation-template.html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>같은 규칙, 바뀐 자료 — 백엔드 실험 다시 보기</title>
<style>
:root{color-scheme:light dark;--bg:#f4f6fa;--panel:#fff;--ink:#18253c;--muted:#506078;--line:#cbd4e1;--accent:#2457c5;--warn:#934400;--warnbg:#fff1df;--good:#16624e;--goodbg:#e6f5ef}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1440px;margin:auto;padding:36px 24px}h1{font-size:clamp(27px,4vw,44px);line-height:1.3;margin:10px 0 16px}h2{font-size:22px}p{max-width:920px}a{color:var(--accent)}.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.04em}.muted,.note{color:var(--muted)}.note{font-size:14px}.controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:22px;background:var(--panel);border:1px solid var(--line);border-radius:16px}label{font-weight:650}select{display:block;width:100%;margin-top:8px;padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);font:inherit}.summary{display:flex;gap:12px;flex-wrap:wrap;padding:20px 0}.pill{border:1px solid var(--line);border-radius:30px;padding:6px 14px;background:var(--panel)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;min-width:0}.card h3{font-size:18px;line-height:1.4;margin:0 0 12px}.badge{font-size:14px;padding:5px 9px;border-radius:6px;display:inline-block;margin-bottom:10px}.good{color:var(--good);background:var(--goodbg)}.warn{color:var(--warn);background:var(--warnbg)}.answer{padding-left:18px;font-size:13px;overflow-wrap:anywhere;max-height:240px;overflow:auto}.hash{font:12px/1.5 ui-monospace,monospace;overflow-wrap:anywhere}.divider{border-top:1px solid var(--line);padding-top:12px;margin-top:14px}.scope{font-size:14px}.foot{margin-top:28px;padding:22px;border-left:4px solid var(--accent);background:var(--panel)}details{margin:12px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.timeline{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 22px}.timeline span{padding:4px 9px;font-size:13px;border-radius:7px;border:1px solid var(--line)}.timeline .active{background:var(--accent);color:#fff;border-color:var(--accent)}@media(max-width:700px){main{padding:24px 14px}.controls{grid-template-columns:1fr;padding:16px}.cards{grid-template-columns:1fr}.answer{max-height:none}}@media(prefers-color-scheme:dark){:root{--bg:#111824;--panel:#1c2738;--ink:#e8edf5;--muted:#bac7da;--line:#43516a;--accent:#91b5ff;--warn:#ffd29d;--warnbg:#4b321f;--good:#9ce7ce;--goodbg:#173e35}}
</style></head><body><main>
<div class="eyebrow">2026-11-06 · 실제 연결 실험의 저장 결과</div>
<h1>같은 규칙, 바뀐 자료</h1>
<p>자료와 계층 규칙을 삭제·복원했을 때 조회 결과와 검토 경고가 어떻게 달라졌는지 살펴봅니다. 아래 선택은 저장된 결과를 표시합니다. DB 연결이나 새 LLM 호출은 없습니다.</p>
<p class="note">기존 개발 자료의 7개 노드·4개 관계와 연구자가 작성한 계층 규칙을 사용했습니다. 160개 결과는 같은 자료의 반복 조건이며 독립 질문 160개가 아닙니다.</p>
<section class="controls" aria-label="실험 조건 선택"><label>변경 상태<select id="event"></select></label><label>조회 계약<select id="query"></select></label><label>보고서 확인 범위<select id="policy"><option value="global">전체 묶음</option><option value="declared_family">질문 유형별 범위</option><option value="swapped_family_control">범위를 뒤바꾼 대조 조건</option><option value="declared_query" selected>조회 대상과 연결 경로</option><option value="swapped_query_control">다른 조회를 연결한 대조 조건</option></select></label></section>
<div class="timeline" id="timeline" aria-label="변경 순서"></div>
<p id="event-description"></p>
<div id="summary" class="summary" aria-live="polite"></div>
<div class="cards" id="cards"></div>
<section class="foot"><h2>보고서가 확인하는 것</h2><p>경고는 사용한 자료와 현재 제공된 자료의 해시가 다르다는 뜻입니다. 답이 틀렸다는 판정은 아닙니다. 질문과 무관한 변경에도 경고가 날 수 있고 확인 범위를 잘못 연결하면 달라진 결과를 놓칠 수 있습니다.</p><p><strong>사후 참조 대조</strong>는 작성한 규칙의 참조 집합과 비교한 평가입니다. 이 표시는 검사기에 주지 않았고 원래 답을 고치는 데 쓰지 않았습니다. 현재 해시도 통제된 실행기가 제공했으며 검사기가 외부 원천의 최신 상태를 알아낸 것은 아닙니다.</p><p>Python·SHACL 보고서는 이 저장 입력에서 같았습니다. 별도 비정상 입력 진단에서는 줄바꿈과 타입 처리의 차이가 나왔습니다. 이 화면은 원래 해시 검사 정책으로 만든 저장 보고서를 보여 주며 나중에 만든 입력 계약으로 교체하지 않습니다.</p><p class="note">외부 추론은 RDFS입니다. Neptune은 도출 결과를 저장·조회했고, n10s는 선택한 계층을 질의 시점에 따라갔습니다. 전체 OWL 동등성·DB 성능·LLM 답변 개선·사람의 검토 시간은 이 화면에서 측정하지 않습니다.</p><a href="../../journal/2026-11-06-backend-inference-review/">전체 실험 보고서</a></section>
<details><summary>원본 파일과 SHA-256</summary><pre id="provenance"></pre></details>
<p class="note">원본 결과 보존 · 자동 차단·답 수정 없음 · 오프라인 재생</p>
</main><script id="saved-evidence" type="application/json">__SAVED_EVIDENCE__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('saved-evidence').textContent);
const eventNames={initial:'처음: 두 경로',delete_primary:'첫 경로 삭제',delete_alternate:'남은 경로 삭제',restore_paths:'경로 복원',delete_fact:'관계 사실 삭제',restore_fact:'관계 사실 복원',delete_schema:'규칙 전체 삭제',restore_schema:'규칙 복원'};
const descriptions={initial:'상위 타입으로 가는 두 경로가 모두 있습니다.',delete_primary:'첫 경로를 지웠지만 다른 경로는 남아 있습니다.',delete_alternate:'상위 타입으로 가는 두 경로를 모두 지웠습니다.',restore_paths:'두 경로를 처음 상태로 복원했습니다.',delete_fact:'선택한 관계 사실 하나를 지웠습니다. 타입 계층 규칙은 유지됩니다.',restore_fact:'삭제한 관계 사실을 복원했습니다.',delete_schema:'타입·관계의 계층 규칙을 모두 지웠습니다.',restore_schema:'계층 규칙을 처음 상태로 복원했습니다.'};
const queryNames={I1_superclass:'I1 · 상위 타입 구성원',I1_unrelated:'I1 · 무관한 타입',I2_forward:'I2 · 상위 관계 정방향',I2_reverse:'I2 · 상위 관계 역방향'};
const armNames={python_current:'Python · 현재 규칙',stale_offline:'오프라인 · 최초 결과 유지',n10s_live_update:'Neo4j+n10s · 현재 조회',neptune_recomputed:'Neptune · 외부 RDFS 재계산',neptune_stale:'Neptune · 최초 결과 유지'};
const familyNames={all:'전체 사실·규칙',type_schema:'타입 사실·타입 계층',relation_schema:'관계 사실·관계 계층',query_dependency:'선택한 조회의 사실·연결 경로'};
const byId=id=>document.getElementById(id);
for(const e of data.events){const o=document.createElement('option');o.value=e;o.textContent=eventNames[e];byId('event').append(o)}
for(const q of data.queries){const o=document.createElement('option');o.value=q;o.textContent=queryNames[q];byId('query').append(o)}
byId('event').value='delete_fact';byId('query').value='I2_forward';
function element(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function shortTerm(x){if(Array.isArray(x))return x.map(shortTerm).join(' → ');if(typeof x==='string')return decodeURIComponent(x.replace('urn:shacl-study:backend:',''));return JSON.stringify(x)}
function render(){
 const event=byId('event').value,query=byId('query').value,policy=byId('policy').value;
 const selected=data.cards.filter(x=>x.event===event&&x.query_id===query);byId('cards').replaceChildren();byId('timeline').replaceChildren();
 for(const e of data.events)byId('timeline').append(element('span',e===event?'active':'',eventNames[e]));
 byId('event-description').textContent=descriptions[event];
 for(const row of selected){
  const report=row.reports[policy],card=element('article','card');card.dataset.arm=row.arm;card.dataset.matches=String(row.matches_declared_reference);card.dataset.review=String(report.review);
  card.append(element('h3','',armNames[row.arm]));card.append(element('div','badge '+(row.matches_declared_reference?'good':'warn'),row.matches_declared_reference?'사후 참조 대조: 일치':'사후 참조 대조: 불일치'));
  card.append(element('p','answer-count','조회 결과 '+row.answer.length+'개'));
  const list=element('ul','answer');if(!row.answer.length)list.append(element('li','','빈 집합'));else for(const answer of row.answer)list.append(element('li','',shortTerm(answer)));card.append(list);
  const section=element('div','divider');section.append(element('strong','',report.review?'검토 경고 있음':'검토 경고 없음'));section.append(element('p','scope','확인 범위: '+familyNames[report.family]));
  const details=element('details');details.append(element('summary','','해시와 보고서 코드'));details.append(element('pre','hash',JSON.stringify({metadata:report.metadata,codes:report.codes},null,2)));section.append(details);card.append(section);byId('cards').append(card);
 }
 const matches=selected.filter(r=>r.matches_declared_reference).length,flags=selected.filter(r=>r.reports[policy].review).length;
 byId('summary').replaceChildren(element('span','pill','표시한 조건 '+selected.length+'개'),element('span','pill','참조 집합 일치 '+matches+'개'),element('span','pill','검토 경고 '+flags+'개'));
}
for(const id of ['event','query','policy'])byId(id).addEventListener('change',render);
byId('provenance').textContent=JSON.stringify(data.source_hashes,null,2);render();
</script><!-- HUMANIZE-SUMMARY: light; gate exit0; change rate0.1%; selfcheck6/6; UI facts preserved. -->
</body></html>
