"""Export an explicitly selected completed run to the public documentation."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    raw = args.run.read_bytes()
    record = json.loads(raw)
    if record['status'] not in {'completed', 'completed_with_errors', 'functional_mismatch'}:
        raise ValueError('Cannot export an unfinished run')
    run_id = record['run_id']
    if Path(run_id).name != run_id:
        raise ValueError('Invalid run identifier')
    public = ROOT / 'docs/experiments/records'
    # Runner records only allowlisted metadata, never env or credentials.
    (public / f'{run_id}.json').write_bytes(raw)
    lines = [f'# {run_id}', '', 'YAGO 4.6 원본 SHACL과 작은 실제 부분집합의 탐색 파일럿. 주입 사례를 포함하며 대표성 있는 성능 평가가 아니다.', '',
             f'- 실행 상태: {record["status"]}', f'- 표본 구분: {record["split"]}',
             f'- LLM 없는 기능 점검: {record["validate_only"]}',
             '- 원본: YAGO 4.6 schema + tiny (CC BY 4.0)',
             f'- 명세: {record["protocol_version"]}',
             f'- SHACL 기대 판정 일치: {record["functional_matches"]}/{len(record["cases"])}',
             f'- Python·SHACL 판정 일치: {record["python_shacl_matches"]}/{len(record["cases"])}', '']
    if record.get('metrics') and record['rows']:
        lines += ['G0: 검증 없음 · G1: 일괄 차단 · G2: 일괄 재검색 · U2: 무조건 재조회 · S1: 선택적 차단 · S2: 선택적 차단과 누락 보완 · C2: 충분성만 검사.', '', '| 조건 | 정답 / 전체 | 응답 중 정답 | 보류 | 오류 | 근거 지지 답변 |',
                  '| --- | --- | --- | --- | --- | --- |']
        for name, m in record['metrics'].items():
            lines.append(f'| {name} | {m["correct"]}/{m["total"]} | {m["correct"]}/{m["answered"]} | {m["abstained"]} | {m["errors"]} | {m["supported_answers"]}/{m["answered"]} |')
        lines += ['', 'G0는 검증 없음, G1은 일괄 차단, G2는 일괄 차단 후 재검색, U2는 무조건 재조회다. S1은 질의 관련 위반만 차단하고 S2는 누락 근거 재검색도 수행한다. C2는 관계의 존재·유일성만 검사하고 재검색한다.', '',
                  f'OpenRouter 호출 시도는 {record["budget"]["calls_attempted"]}회이며 응답에 기록된 비용 합계는 {record["budget"]["cost_usd_reported"]:.8f} USD다. 비용 누락 응답은 {record["budget"]["missing_cost_responses"]}건이다.', '',
                  '근거 지지는 제시된 근거 안에서 답변 값과 인용이 일치하는지 확인한 결과다. 주입된 사실 오류를 인용해도 근거 지지는 통과할 수 있다. 정답 정확도와 구분한다.', '',
                  '첫 근거 검색은 조건별 실행 전에 공유한다. total_ms는 그 이후의 검사·재검색·생성·파일 저장 시간을 포함하며 배치 전처리와 첫 검색 시간은 제외한다. 단일 실행 시간으로 엔진 성능을 비교하지 않는다.', '']
    if record.get('metrics') and record['rows']:
        lines += ['', '| 조건 | 오답 | 불필요한 보류 / 답변 가능한 원천 | 원천 누락 보류 |', '| --- | --- | --- | --- |']
        denominator = sum(c['source_answerable'] for c in record['cases'])
        for name, m in record['metrics'].items():
            lines.append(f'| {name} | {m["wrong_answers"]} | {m["unnecessary_abstentions"]}/{denominator} | {m["unknown_source_abstentions"]} |')
        lines += ['', '원천 누락에서의 보류는 정답 URI 응답 수와 별도로 집계한다. 불필요한 보류의 분모는 명세 0.4에서 사전에 정한 답변 가능한 원천 사례다.', '']
    lines += [f'[전체 판정·답변·사용량 JSON]({run_id}.json) · [실험 명세](../specification.md) · [실행 목록](index.md)', '']
    (public / f'{run_id}.md').write_text('\n'.join(lines))
    index = public / 'index.md'
    text = index.read_text()
    entry = f'- [{run_id}]({run_id}.md) — {record["status"]}, {record["split"]}'
    if f']({run_id}.md)' not in text:
        index.write_text(text.replace('<!-- RUNS -->', '<!-- RUNS -->\n\n' + entry, 1))
    print(public / f'{run_id}.md')


if __name__ == '__main__':
    main()
