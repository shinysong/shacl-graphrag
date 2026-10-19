"""Standalone, read-only viewer of saved paired finite-witness audits.

Paths retain the evaluators' working-directory semantics. No scoring or model calls.
"""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path

from render_nl2shacl_tier_report import collect, key, load, sha, HTML as TIER_HTML


OUTCOMES = {'agreement', 'underconstraint_observed', 'overconstraint_observed', 'unavailable'}


def check_saved_result(result, probes):
    """Reject inconsistent stored claims; never execute or replace any verdict."""
    status = result.get('status')
    if status not in ('evaluated', 'unavailable'):
        raise ValueError('Saved result status mismatch')
    if status == 'evaluated':
        if result.get('unavailable_witnesses'):
            raise ValueError('Saved witness container mismatch')
        outcomes = result.get('witnesses', [])
    else:
        if result.get('witnesses'):
            raise ValueError('Saved unavailable container mismatch')
        outcomes = result.get('unavailable_witnesses', [])
    if [p['id'] for p in outcomes] != [p['id'] for p in probes]:
        raise ValueError('Result witness binding mismatch')
    for row, probe in zip(outcomes, probes):
        if type(row.get('expected_reference_conforms')) is not bool or row['expected_reference_conforms'] != probe['expected_reference_conforms']:
            raise ValueError('Expectation binding mismatch')
        if row.get('status') == 'observed':
            if status != 'evaluated' or type(row.get('conforms')) is not bool:
                raise ValueError('Saved observed verdict mismatch')
            # This checks a saved assertion's internal consistency only; no SHACL
            # or truth scoring is performed and the saved outcome is never edited.
            allowed = ('agreement' if row['conforms'] == row['expected_reference_conforms']
                       else 'underconstraint_observed' if row['conforms'] else 'overconstraint_observed')
            if row.get('outcome') != allowed:
                raise ValueError('Saved observed outcome mismatch')
        elif row.get('status') == 'unavailable':
            if 'conforms' in row or row.get('outcome') != 'unavailable':
                raise ValueError('Saved unavailable verdict mismatch')
        else:
            raise ValueError('Saved witness status mismatch')
    counts = result.get('counts', {})
    observed_counts = Counter(p['outcome'] for p in outcomes)
    if set(counts) != OUTCOMES or any(type(v) is not int or v < 0 or observed_counts.get(k, 0) != v for k, v in counts.items()):
        raise ValueError('Saved count mismatch')
    return observed_counts


def pair_index(packet):
    rows = packet if isinstance(packet, list) else packet['pairs']
    indexed = {row['id']: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate requirement pair')
    return indexed


def collect_witnesses(audit, inputs, ledger, normalized, pairs=None):
    """The caller must hold the shared ledger lock through the final hash check."""
    data, tracked = collect(audit, inputs, ledger)

    def verify(path, expected=None):
        path = str(Path(path).resolve())
        value = sha(path)  # Dependencies may be binary: never decode merely to hash.
        if (expected is not None and value != expected) or (path in tracked and tracked[path] != value):
            raise ValueError('Hash mismatch: ' + path)
        tracked[path] = value
        return path

    def dependencies(record):
        hashes = {str(Path(p).resolve()): h for p, h in record['hashes'].items()}
        for path, expected in hashes.items():
            verify(path, expected)
        return hashes

    supplied_pairs = pair_index(load(verify(pairs))) if pairs else None
    cases = {}
    for path in normalized:
        record = load(verify(path))
        if record['protocol'] != 'nl2shacl-original-postprocessing-witness-audit-1':
            raise ValueError('Unexpected normalized protocol')
        hashes = dependencies(record)
        for bound in (audit, inputs, ledger, record['design'], record['raw_results']):
            name = str(Path(bound).resolve())
            if name not in hashes:
                raise ValueError('Missing normalized dependency binding: ' + name)
            verify(name, hashes[name])
        if Path(record['audit']).resolve() != Path(audit).resolve():
            raise ValueError('Audit binding mismatch')
        design = load(record['design'])
        old = load(record['raw_results'])
        old_hashes = dependencies(old)
        if old['protocol'] != 'nl2shacl-finite-witness-audit-1':
            raise ValueError('Unexpected raw protocol')
        for field, expected in [('audit', audit), ('design', record['design'])]:
            name = str(Path(expected).resolve())
            if Path(old[field]).resolve() != Path(expected).resolve() or old_hashes.get(name) != sha(expected):
                raise ValueError('Raw binding mismatch')
        if record['validation_options'] != design['validation_options'] or old['validation_options'] != design['validation_options']:
            raise ValueError('Validation options binding mismatch')
        case = design['case_id']
        if case in cases:
            raise ValueError('Duplicate case')
        probes = []
        for p in design['witnesses']:
            name = str(Path(p['data_path']).resolve())
            if hashes.get(name) != p['sha256'] or type(p['expected_reference_conforms']) is not bool:
                raise ValueError('Witness binding mismatch')
            probes.append({**p, 'ttl': Path(verify(name, p['sha256'])).read_text(encoding='utf-8')})
        if not probes or len({p['id'] for p in probes}) != len(probes):
            raise ValueError('Empty or duplicate witnesses')
        for name, digest in [(design['reference_path'], design['reference_sha256']), (design['source_pairs_path'], design['source_pairs_sha256'])]:
            if hashes.get(str(Path(name).resolve())) != digest:
                raise ValueError('Design dependency binding mismatch')
            verify(name, digest)
        selected = {key(r): r for r in data['rows'] if r['id'] == case}
        if supplied_pairs is not None:
            original_pairs = pair_index(load(design['source_pairs_path']))
            original_pair, supplied_pair = original_pairs.get(case), supplied_pairs.get(case)
            if original_pair is None or supplied_pair is None:
                raise ValueError('Missing requirement pair')
            languages = {'en', 'ko'} & (set(original_pair) | set(supplied_pair))
            if not languages or any(original_pair.get(lang) != supplied_pair.get(lang) for lang in languages):
                raise ValueError('Pair content binding mismatch')
            for source in selected.values():
                requirement = supplied_pair.get(source['language'])
                if not isinstance(requirement, str) or requirement not in source['user_prompt']:
                    raise ValueError('Requirement prompt binding mismatch')
                source['requirement'] = requirement
        rows = {key(r): r for r in record['rows']}
        originals = {key(r): r for r in old['rows']}
        if not selected or len(rows) != len(record['rows']) or set(rows) != set(selected):
            raise ValueError('Normalized row binding mismatch')
        attempted = {k for k, r in selected.items() if r['status'] != 'unexecuted'}
        if len(originals) != len(old['rows']) or set(originals) != attempted:
            raise ValueError('Raw row binding mismatch')
        totals = {'raw': Counter(), 'normalized': Counter()}
        for k, row in rows.items():
            source = selected[k]
            if row['status'] != source['status']:
                raise ValueError('Status binding mismatch')
            if source['status'] == 'unexecuted':
                if row['raw_result'] is not None or row['normalized_result'] is not None or row['pipeline_status'] != 'unexecuted':
                    raise ValueError('Unexecuted result mismatch')
            else:
                if (row['reservation_index'] != source['reservation_index']
                        or originals[k]['reservation_index'] != source['reservation_index']
                        or originals[k]['audit_raw_meta'] != source['meta']
                        or row['raw_result'] != originals[k]['result']):
                    raise ValueError('Raw result binding mismatch')
                if source['status'] == 'completed':
                    for field in ('raw_sha256', 'cleaned_sha256', 'reference_sha256'):
                        if row[field] != source[field]:
                            raise ValueError('Candidate binding mismatch')
                    if row['reference_sha256'] != design['reference_sha256']:
                        raise ValueError('Reference binding mismatch')
                expected_pipeline = 'terminal_provider_failure' if source['status'] == 'failed' else row['normalized_result'].get('status')
                if row['pipeline_status'] != expected_pipeline:
                    raise ValueError('Pipeline status mismatch')
                for arm in totals:
                    result = row[arm + '_result']
                    counts = check_saved_result(result, probes)
                    if source['status'] == 'failed' and (result.get('status') != 'unavailable' or result.get('reason') != 'terminal_provider_failure' or counts != Counter(unavailable=len(probes))):
                        raise ValueError('Failure result mismatch')
                    totals[arm].update(result['counts'])
            source['witness_result'] = row
        expected = dict(planned=len(selected), attempted=len(attempted), completed=sum(r['status']=='completed' for r in selected.values()), failed=sum(r['status']=='failed' for r in selected.values()), unexecuted=len(selected)-len(attempted), witnesses_per_attempt=len(probes))
        if record['denominators'] != expected or any(dict(totals[a]) != record['summary'][a] for a in totals):
            raise ValueError('Denominator or summary mismatch')
        cases[case] = dict(probes=probes, denominators=record['denominators'], summary=record['summary'], limits=record['limits'])
    if not cases:
        raise ValueError('No normalized inputs')
    data['cases'] = cases
    data['rows'] = [r for r in data['rows'] if r['id'] in cases]
    data['provenance'] = tracked
    return data, tracked


STYLE = TIER_HTML.split('<style>', 1)[1].split('</style>', 1)[0] + '\nmain{overflow-wrap:anywhere}select{max-width:100%}'
HTML = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>NL2SHACL · 증거 데이터 비교</title><style>__STYLE__</style><main>
<h1>원문·정리본 증거 데이터 비교</h1><p class="notice">유한 검사 사례 · 참조 기준 비교 · 부분 표본 · 의미 동등성·모델 순위 아님 · 미실행은 오답 아님</p>
<p id="notice"></p><p id="totals"></p><p id="availability"></p>
<div id="casebar"><label>사례 <select id="case"></select></label><label>언어 <select id="language"><option value="ko">한국어</option><option value="en">영어</option></select></label><label>검사 사례 <select id="probe"></select></label></div>
<section><h2>선택 검사 사례 · 실제 데이터</h2><p id="expectation"></p><pre id="ttl"></pre><details><summary>요구사항</summary><pre id="requirement"></pre></details><details><summary>참조 SHACL</summary><pre id="reference"></pre></details><details><summary>사례 전체 집계·범위</summary><pre id="summary"></pre></details></section>
<div id="cards"></div><details><summary>출처·검증 해시</summary><pre id="provenance"></pre></details>
<noscript>사례 선택에는 JavaScript가 필요합니다.</noscript></main><script type="application/json" id="data">__DATA__</script><script>
'use strict';const data=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id),show=x=>x===null||x===undefined?'미보고':typeof x==='object'?JSON.stringify(x,null,2):String(x);
function node(tag,text,parent){const n=document.createElement(tag);n.textContent=text;if(parent)parent.append(n);return n;}
function detail(parent,label,value){const d=node('details','',parent);node('summary',label,d);node('pre',show(value),d);}
const labels={agreement:'참조 일치',underconstraint_observed:'위반 데이터 통과',overconstraint_observed:'정상 데이터 거절',unavailable:'평가 불가'};
const verdict=x=>x===true?'적합':x===false?'부적합':'미판정';
function counts(r){return r?Object.entries(r.counts).map(([k,v])=>(labels[k]||k)+' '+v).join(' · '):'미실행';}
for(const id of Object.keys(data.cases)){const o=node('option',id,el('case'));o.value=id;}
const order=['openai/gpt-6-astra','openai/gpt-6-luna','anthropic/claude-opus-5.5','anthropic/claude-haiku-5.5','google/gemini-4-argon','google/gemini-3.8-flash','qwen/qwen3.8-max-0902','qwen/qwen3.8-flash'];
function probes(){el('probe').replaceChildren();for(const p of data.cases[el('case').value].probes){const o=node('option',p.id,el('probe'));o.value=p.id;}render();}
function render(){const id=el('case').value,c=data.cases[id],p=c.probes.find(p=>p.id===el('probe').value),rows=data.rows.filter(r=>r.id===id&&r.language===el('language').value);
rows.sort((a,b)=>(order.indexOf(a.model)<0?99:order.indexOf(a.model))-(order.indexOf(b.model)<0?99:order.indexOf(b.model)));
el('availability').textContent='사례 전체 · 원문: '+counts({counts:c.summary.raw})+' / 정리본: '+counts({counts:c.summary.normalized})+' · 미실행 '+c.denominators.unexecuted;
el('notice').textContent=id==='chemrof-2'?'입력 제한 · chemrof-2 프롬프트에 참조 열거 식별자 4개 누락':'';
el('ttl').textContent=p.ttl;el('expectation').textContent='참조 예상 판정: '+verdict(p.expected_reference_conforms);el('summary').textContent=show(c);
el('requirement').textContent=rows[0]?.requirement??'요구사항 쌍 미제공 · 카드 프롬프트 확인';el('reference').textContent=rows.find(r=>r.reference)?.reference??'자료 없음';
el('cards').replaceChildren();for(const r of rows){const card=node('article','',el('cards')),w=r.witness_result;node('h2',r.model,card);
node('p',r.status==='failed'?'호출 실패 · 평가 불가':r.status==='unexecuted'?'미실행 · 평가 제외':r.classification==='truncation'?'출력 잘림':'생성 완료',card);
node('p','원문 파싱·메타: '+show(r.meta?.status),card);node('p','정리본 처리: '+show(w.pipeline_status)+' · '+show(w.postprocessing_change),card);
for(const [arm,label] of [['raw','원문'],['normalized','정리본']]){const result=w[arm+'_result'],v=(result?.witnesses||result?.unavailable_witnesses||[]).find(x=>x.id===p.id);node('p',label+' 전체: '+counts(result),card);node('p',label+' 선택 판정: '+verdict(v?.conforms)+' · '+(labels[v?.outcome]||'미실행')+(v?.reason?' · '+v.reason:''),card);detail(card,label+' 선택 검사 사례 보고서',v);detail(card,label+' 전체 보고서',result);}
detail(card,'모델 생성 원문',r.raw);detail(card,'원본 후처리 정리본',r.cleaned);detail(card,'전체 프롬프트',{system:r.system_prompt,user:r.user_prompt});detail(card,'원문 감사·호출 정보',{meta:r.meta,finish_reason:r.finish_reason,classification:r.classification,provider:r.provider});}}
el('case').onchange=probes;el('language').onchange=render;el('probe').onchange=render;el('totals').textContent='전체 호출 계획 '+data.totals.planned+' · 호출 '+data.totals.attempts+' · 완료 '+data.totals.completed;el('provenance').textContent=show(data.provenance);probes();
</script></html>'''.replace('__STYLE__', STYLE)


def render(data):
    encoded = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return HTML.replace('__DATA__', encoded)


def run(audit, inputs, ledger, normalized, output, pairs=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    with Path(ledger).with_suffix('.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Ledger is busy') from exc
        data, tracked = collect_witnesses(audit, inputs, ledger, normalized, pairs)
        html = render(data)
        if any(sha(p) != h for p, h in tracked.items()):
            raise ValueError('Inputs changed while rendering')
        with output.open('x', encoding='utf-8') as stream:
            stream.write(html)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('audit', 'inputs', 'ledger', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--normalized', type=Path, action='append', required=True)
    parser.add_argument('--pairs', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args))['totals'], ensure_ascii=False))
