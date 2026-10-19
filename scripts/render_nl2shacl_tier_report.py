"""Read-only, offline HTML viewer for a quiescent, hash-bound NL2SHACL audit.

Run from the same working directory as the auditor (its paths are cwd-relative).
No validation/scoring or generation is performed. The output must be a new file.
"""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def key(row):
    return row['model'], row['id'], row['language']


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def collect(audit_path, inputs_path, ledger_path, pairs_path=None):
    """Caller holds the runner's ledger lock until the final integrity check."""
    audit, inputs, ledger = load(audit_path), load(inputs_path), load(ledger_path)
    tracked = {str(Path(p).resolve()): sha(p) for p in (audit_path, inputs_path, ledger_path)}
    hashes = {str(Path(p).resolve()): h for p, h in audit['hashes'].items()}
    if Path(audit['ledger']).resolve() != Path(ledger_path).resolve() or hashes.get(str(Path(ledger_path).resolve())) != sha(ledger_path):
        raise ValueError('Audit ledger hash mismatch')
    for name, expected in hashes.items():
        if sha(name) != expected:
            raise ValueError('Audit artifact hash mismatch: ' + name)
    tracked.update(hashes)
    reservations = ledger['reservations']
    if any(r['status'] not in ('completed', 'failed') for r in reservations):
        raise ValueError('Ledger is not quiescent: unresolved reservation')
    if ledger['attempts'] != len(reservations):
        raise ValueError('Ledger attempt mismatch')
    by_input = {key(r): r for r in inputs}
    by_audit = {key(r): r for r in audit['rows']}
    if len(by_input) != len(inputs) or len(by_audit) != len(audit['rows']) or len({key(r) for r in reservations}) != len(reservations):
        raise ValueError('Duplicate row')
    if set(by_audit) != {key(r) for r in reservations}:
        raise ValueError('Audit row mismatch')
    pairs, attribution = {}, {}
    if pairs_path:
        packet = load(pairs_path)
        tracked[str(Path(pairs_path).resolve())] = sha(pairs_path)
        pairs = {p['id']: p for p in packet['pairs']}
        attribution = {k: v for k, v in packet.items() if k != 'pairs'}
    processed, evaluated = {}, {}
    for run in audit['upstream_runs']:
        path = Path(run['processed_input'])
        if str(path.resolve()) not in hashes:
            raise ValueError('Unhashed processed artifact')
        if run.get('status') == 'completed':
            eval_path = path.parent / 'upstream' / path.name.replace('_processed.jsonl', '_eval.jsonl')
            if str(eval_path.resolve()) not in hashes:
                raise ValueError('Unhashed upstream result')
            for line in eval_path.read_text().splitlines():
                score = json.loads(line)
                score_key = (run['model'], score['id'])
                if score_key in evaluated:
                    raise ValueError('Duplicate upstream row')
                evaluated[score_key] = {f: score[f] for f in ('status', 'validity', 'structural')}
        for line in path.read_text().splitlines():
            record = json.loads(line)
            k = (run['model'], record['id'])
            if k in processed:
                raise ValueError('Duplicate processed row')
            processed[k] = record
    rows = []
    for index, reservation in enumerate(reservations):
        k = key(reservation)
        if k not in by_input or digest(by_input[k]) != reservation['input_sha256']:
            raise ValueError('Frozen input hash mismatch')
        row = by_audit[k]
        if row['reservation_index'] != index or any(row.get(f) != reservation.get(f) for f in ('status', 'reported_usd', 'upper_usd')):
            raise ValueError('Audit reservation mismatch')
    for prompt in inputs:
        k = key(prompt)
        row = dict(by_audit.get(k, {'status': 'unexecuted', 'meta': {'status': 'not_evaluated'}}))
        row.update(prompt)
        pair = pairs.get(prompt['id'])
        if pairs_path and pair is None:
            raise ValueError('Missing requirement pair')
        row['requirement'] = pair[prompt['language']] if pair else None
        if pair and row['requirement'] not in prompt['user_prompt']:
            raise ValueError('Requirement does not match frozen prompt')
        if k in by_audit:
            index = row['reservation_index']
            reservation = reservations[index]
            row['latency_seconds'] = reservation.get('latency_seconds')
            if row['status'] == 'completed':
                folder = Path(ledger['output']) / f'call-{index:04d}'
                raw_path, response_path = folder / 'output.ttl', folder / 'response.json'
                for path in (raw_path, response_path):
                    if str(path.resolve()) not in hashes:
                        raise ValueError('Unhashed raw artifact')
                raw, response = raw_path.read_text(), load(response_path)
                choice = response['choices'][0]
                if choice['message']['content'] != raw or sha(raw_path) != row['raw_sha256']:
                    raise ValueError('Raw output mismatch')
                if any(row.get(f) != response.get(f) for f in ('usage', 'provider')) or row.get('response_model') != response.get('model') or row.get('finish_reason') != choice.get('finish_reason'):
                    raise ValueError('Audit response mismatch')
                if response.get('usage', {}).get('cost') != reservation['reported_usd']:
                    raise ValueError('Reported cost mismatch')
                artifact_key = (prompt['model'], prompt['id'] + '-' + prompt['language'])
                if row.get('upstream') != evaluated.get(artifact_key):
                    raise ValueError('Audit upstream result mismatch')
                record = processed[artifact_key]
                for field, expected in [('reference_shacl', row['reference_sha256']), ('output_shacl', row['cleaned_sha256'])]:
                    if hashlib.sha256(record[field].encode()).hexdigest() != expected:
                        raise ValueError('Processed content hash mismatch')
                if row['reference_sha256'] not in audit['source_hashes'].values():
                    raise ValueError('Unpinned reference')
                row.update(raw=raw, reference=record['reference_shacl'], cleaned=record['output_shacl'])
                row['reasoning_tokens'] = (response.get('usage', {}).get('completion_tokens_details') or {}).get('reasoning_tokens')
        rows.append(row)
    known = [r['reported_usd'] for r in reservations if r.get('reported_usd') is not None]
    data = dict(rows=rows, attribution=attribution, provenance=tracked,
                totals=dict(planned=len(inputs), attempts=len(reservations), completed=sum(r['status'] == 'completed' for r in reservations),
                            reported_usd=str(sum((Decimal(str(v)) for v in known), Decimal(0))),
                            unresolved_costs=len(reservations)-len(known),
                            reserved_usd=str(sum((max(Decimal(str(r['upper_usd'])), Decimal(str(r.get('reported_usd') or 0))) for r in reservations), Decimal(0)))))
    return data, tracked


HTML = '''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>NL2SHACL · 모델 비교</title>
<style>
:root{color-scheme:light dark;--bg:#f3f5fa;--card:#fff;--fg:#182638;--line:#9baaba;--accent:#2456a6}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}main{max-width:1700px;margin:auto;padding:24px}h1{font-size:2rem}h2{font-size:1.1rem;overflow-wrap:anywhere}p{max-width:100ch}.notice{border-left:5px solid var(--accent);padding:12px;background:var(--card)}#cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}article,section{background:var(--card);padding:16px;border:1px solid var(--line);border-radius:12px;margin-bottom:16px;min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace;max-height:28rem;overflow:auto}button,select{font:inherit;padding:8px;margin:4px;border:1px solid var(--line);border-radius:8px;color:var(--fg);background:var(--card)}button[aria-pressed=true]{outline:3px solid var(--accent)}:focus-visible{outline:3px solid var(--accent)}summary{cursor:pointer;font-weight:600;margin:10px 0}.metrics{font-size:14px}#casebar{margin:20px 0}footer{overflow-wrap:anywhere}details{min-width:0}@media(max-width:1100px){#cards{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){main{padding:12px}#cards{grid-template-columns:1fr}}@media(prefers-color-scheme:dark){:root{--bg:#101927;--card:#1c2a3e;--fg:#eef3fc;--line:#70829b;--accent:#8eb8ff}}@media print{#cards{display:block}article{break-inside:avoid}pre{max-height:none}button,select{display:none}body{background:white;color:black}}
</style><main><h1>NL2SHACL · 모델 비교</h1>
<p class="notice"><strong>의미적 정답률 미측정 · 구조 일치 ≠ 의미 일치</strong><br>소규모 탐색 표본 · 미실행은 오답이 아님 · 잘린 출력은 별도 표시</p>
<p>요구사항 → 모델 생성 SHACL → 원문 파싱·메타 검사 → 정리본 구조 비교</p>
<p>메타 검사는 SHACL 형식 검사입니다. 구조 비교는 원본 평가기의 결과입니다. 참조 SHACL은 생성 후 비교에만 사용했습니다.</p>
<section><h2>실행·비용</h2><p id="totals"></p><p>보고 비용과 미환급 예약액은 다릅니다. 추론 토큰 0은 내부 추론 부재의 증거가 아닙니다. 시간은 요청별 관측값이며 반복 성능 측정이 아닙니다.</p></section>
<div id="casebar"><label for="case">사례 </label><select id="case"></select><span id="languages" role="group" aria-label="언어"></span><span id="filters" role="group" aria-label="결과 필터"></span></div>
<section><h2>원문 요구사항</h2><pre id="requirement"></pre><details><summary>참조 SHACL · 생성 후 비교</summary><pre id="reference"></pre></details></section>
<p id="count" aria-live="polite"></p><div id="cards"></div><footer><details><summary>출처·검증 해시</summary><pre id="provenance"></pre></details></footer>
<noscript>이 로컬 보고서의 사례 선택에는 JavaScript가 필요합니다.</noscript></main>
<script type="application/json" id="data">__DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const el=id=>document.getElementById(id), show=v=>v===undefined||v===null?'미보고':typeof v==='object'?JSON.stringify(v,null,2):String(v);
function node(tag,text,parent){const n=document.createElement(tag);n.textContent=text;if(parent)parent.append(n);return n;}
function detail(parent,label,value,open=false){const d=node('details','',parent);d.open=open;node('summary',label,d);node('pre',show(value),d);}
let language='ko',filter='all';
const ids=[...new Set(data.rows.map(r=>r.id))];for(const id of ids){const o=node('option',id,el('case'));o.value=id;}
function chips(target,options,current,action){el(target).replaceChildren();for(const [value,label] of options){const b=node('button',label,el(target));b.type='button';b.setAttribute('aria-pressed',String(value===current));b.onclick=()=>action(value);}}
const tiers={'openai/gpt-6-astra':'OpenAI · 프런티어','openai/gpt-6-luna':'OpenAI · 저비용','anthropic/claude-opus-5.5':'Anthropic · 프런티어','anthropic/claude-haiku-5.5':'Anthropic · 저비용','google/gemini-4-argon':'Google · 프런티어','google/gemini-3.8-flash':'Google · 저비용','qwen/qwen3.8-max-0902':'Qwen · 프런티어','qwen/qwen3.8-flash':'Qwen · 저비용'};
const order=Object.keys(tiers);
function render(){
chips('languages',[['ko','한국어'],['en','English']],language,v=>{language=v;render()});
chips('filters',[['all','전체'],['issue','파싱·메타 문제·미확정'],['truncated','잘림'],['missing','미완료']],filter,v=>{filter=v;render()});
const selected=data.rows.filter(r=>r.id===el('case').value&&r.language===language);
el('requirement').textContent=selected[0]?.requirement??'원문 쌍 미제공 · 각 카드의 전체 프롬프트 확인';
el('reference').textContent=selected.find(r=>r.reference)?.reference??'비교 자료 없음';
let rows=selected.filter(r=>filter==='all'||filter==='issue'&&['parse_failure','invalid_shape','runtime_exception','unknown'].includes(r.meta?.status)||filter==='truncated'&&r.classification==='truncation'||filter==='missing'&&r.status!=='completed');
rows.sort((a,b)=>(order.indexOf(a.model)<0?99:order.indexOf(a.model))-(order.indexOf(b.model)<0?99:order.indexOf(b.model)));
el('count').textContent=`${el('case').value} · ${language} · ${rows.length} / ${selected.length} 모델`;
el('cards').replaceChildren();for(const r of rows){const card=node('article','',el('cards'));node('h2',(tiers[r.model]||'모델')+' · '+r.model,card);
node('p',r.status==='unexecuted'?'미실행 · 오답 아님':r.status==='failed'?'호출 실패 · 의미 평가 없음':r.classification==='truncation'?'출력 잘림':r.status,card);
node('p',`USD ${show(r.reported_usd)} · ${show(r.latency_seconds)}초 · 추론 ${show(r.reasoning_tokens)} 토큰`,card).className='metrics';
node('p',`파싱·메타: ${show(r.meta?.status)} · 구조 일치: ${show(r.upstream?.structural?.isomorphic)}`,card);
detail(card,'1 · 실제 입력 프롬프트',{system:r.system_prompt,user:r.user_prompt});detail(card,'2 · 모델 생성 SHACL 원문',r.raw??'완료된 원문 없음',true);
detail(card,'3 · 원문 파싱·메타 검사',r.meta);detail(card,'4 · 원본 구조 비교',{result:r.upstream??'미실행',postprocessing_changed_nonwhitespace:r.postprocessing_changed_nonwhitespace});
detail(card,'정리본 · 구조 비교 입력',r.cleaned??'없음');detail(card,'호출 메타데이터',{provider:r.provider,response_model:r.response_model,finish_reason:r.finish_reason,usage:r.usage,upper_usd:r.upper_usd,raw_sha256:r.raw_sha256,reference_sha256:r.reference_sha256});}}
el('case').onchange=render;const t=data.totals;el('totals').textContent=`계획 ${t.planned} · 예약 호출 ${t.attempts} · 완료 ${t.completed} · 보고 USD ${t.reported_usd} · 미확정 비용 ${t.unresolved_costs}건 · 미환급 예약 USD ${t.reserved_usd}`;
el('provenance').textContent=show({attribution:data.attribution,hashes:data.provenance});render();
</script></html>'''


def render(data):
    # JSON is embedded as inert text; all dynamic DOM writes use textContent.
    encoded = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return HTML.replace('__DATA__', encoded)


def run(audit, inputs, ledger, output, pairs=None):
    output, ledger = Path(output), Path(ledger)
    if output.exists():
        raise FileExistsError(output)
    with ledger.with_suffix('.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Ledger is busy') from exc
        data, tracked = collect(audit, inputs, ledger, pairs)
        html = render(data)
        if any(sha(path) != expected for path, expected in tracked.items()):
            raise ValueError('Inputs changed while rendering')
        with output.open('x', encoding='utf-8') as stream:
            stream.write(html)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('audit', 'inputs', 'ledger', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--pairs', type=Path)
    args = parser.parse_args()
    result = run(args.audit, args.inputs, args.ledger, args.output, args.pairs)
    print(json.dumps(result['totals'], ensure_ascii=False))
