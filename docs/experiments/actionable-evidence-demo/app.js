'use strict';
(() => {
  const data = window.ACTIONABLE_DEMO;
  const $ = id => document.getElementById(id);
  const stages = ['input-panel', 'relations-panel', 'candidate-panel', 'report-panel', 'decision-panel'];
  const stageLabels = ['입력', '관계 근거', '후보·요청', '점검 기록', '최종 상태'];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let timers = [];
  const json = value => JSON.stringify(value, null, 2);
  const show = value => typeof value === 'string' ? value : json(value);
  const put = (id, value) => { $(id).textContent = value == null ? '' : show(value); };
  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text != null) el.textContent = show(text);
    if (cls) el.className = cls;
    return el;
  }
  function table(container, value) {
    container.replaceChildren();
    if (value == null) { container.append(node('p', '기록 없음', 'muted')); return; }
    const tbl = node('table');
    const head = node('thead'), row = node('tr');
    ['필드', '저장된 값'].forEach(x => { const th = node('th', x); th.scope = 'col'; row.append(th); });
    head.append(row); tbl.append(head);
    const body = node('tbody');
    const entries = typeof value === 'object' ? Object.entries(value) : [['value', value]];
    entries.forEach(([key, val]) => {
      const tr = node('tr'), th = node('th', key), td = node('td'); th.scope = 'row';
      td.append(node(typeof val === 'object' && val !== null ? 'pre' : 'span', val));
      tr.append(th, td); body.append(tr);
    });
    tbl.append(body); container.append(tbl);
  }
  function list(container, values) {
    const ul = node('ul'); (values || []).forEach(value => ul.append(node('li', value))); container.append(ul);
  }
  function cancelPlayback(announce = false) {
    timers.forEach(clearTimeout); timers = [];
    stages.forEach(id => $(id).classList.remove('active'));
    $('replay').textContent = '저장된 흐름 따라가기';
    if (announce) put('playback-status', '재생을 중지했습니다. 모든 단계가 표시되어 있습니다.');
  }
  function options(id, values) {
    values.forEach(value => { const opt = node('option', value.label); opt.value = value.id; $(id).append(opt); });
  }
  function report(prefix, value) {
    const conformity = value?.shacl?.conforms;
    put(`${prefix}-conforms`, conformity === true ? 'SHACL conforms: true · 선언 조건 충족' : conformity === false ? 'SHACL conforms: false · 선언 조건 위반' : '수정 후보가 없어 변경 후 검사 없음');
    put(`${prefix}-json`, json(value ?? null));
    const box = $(`${prefix}-summary`); box.replaceChildren();
    if (value) {
      box.append(node('p', `Python conforms: ${String(value.python?.conforms ?? '기록 없음')} · validators_agree: ${String(value.validators_agree ?? '기록 없음')}`, 'small'));
      list(box, value.shacl?.results);
    }
  }
  function provenance(caseData) {
    const box = $('provenance'); box.replaceChildren();
    (caseData.provenance || []).forEach(source => {
      const item = node('div', null, 'source');
      item.append(node('strong', source.label), node('p', source.locator), node('code', `SHA-256: ${source.sha256 ?? '기록 없음'}`));
      if (typeof source.url === 'string' && /^https?:\/\//i.test(source.url)) {
        const p = node('p'), a = node('a', '원자료 열기'); a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; p.append(a); item.append(p);
      }
      box.append(item);
    });
  }
  function render() {
    cancelPlayback();
    const c = data.cases.find(item => item.id === $('case-select').value);
    const real = c.kind === 'real_audit';
    document.body.dataset.caseId = c.id;
    document.body.dataset.arm = $('arm-select').value;
    document.body.dataset.postcheck = $('postcheck-select').value;
    $('case-select').querySelectorAll('option').forEach(opt => { opt.dataset.selected = String(opt.value === c.id); });
    ['arm-select', 'postcheck-select'].forEach(id => { $(id).disabled = real; });
    $('replay').disabled = real;
    put('playback-status', real ? '실제 자료의 기술적 감사 사례입니다. 실행 결과 없이 연구자가 작성한 확인 요청을 표시합니다.' : '모든 단계가 표시되어 있습니다. 재생은 저장된 기록을 순서대로 강조합니다.');
    put('case-kind', real ? '실제 자료 · 확인 요청' : '합성 사례 · 저장된 실행');
    put('case-title', c.label); put('question', c.question); put('case-note', c.note);
    const inputSummary = real ? {
      coupon: c.input.coupon, sheet: c.input.sheet, cell_range: c.input.cell_range, ...c.input.values
    } : {target: c.input.target, nodes_count: c.input.nodes.length};
    if (real && c.input.coupon === 'PP7') {
      inputSummary['주석 코드의 명목 설정'] = `코드 ${c.input.values.welding_setting} · DC ${c.input.observed_nominal_setting[1]} A`;
      inputSummary['설계 대응 명목 설정'] = `코드 ${c.input.design_expected_setting_code} · DC ${c.input.design_nominal_setting[1]} A`;
      inputSummary['설정값의 의미'] = '두 값은 명목 설정이며 측정값이 아닙니다.';
    }
    table($('input-table'), inputSummary); put('source-json', json(c.input));
    put('input-json', json(real ? c.input : c.runtime));
    put('input-json-label', real ? '원자료 JSON' : '실행 입력 JSON · 평가 라벨 제외');
    $('source-details').hidden = real;
    const relationBox = $('relations'); relationBox.replaceChildren();
    const relationList = node('ul', null, 'relations-list');
    (c.relations || []).forEach(item => {
      const li = node('li'); li.append(node('strong', item.from), node('span', `↓ ${item.relation}`, 'relation'), node('span', item.to)); relationList.append(li);
    });
    relationBox.append(relationList);
    if (!c.relations?.length) relationBox.append(node('p', '표시할 관계 기록이 없습니다.', 'muted'));
    ['candidate-summary', 'decision-summary'].forEach(id => $(id).replaceChildren());
    $('candidate-details').hidden = real; $('output-details').hidden = real; $('report-content').hidden = real; $('evaluation-panel').hidden = real;
    provenance(c);
    if (real) {
      const request = c.request;
      put('candidate-title', request.title); put('report-title', '확인 요청의 범위'); put('decision-title', '연구자 확인 요청');
      $('candidate-summary').append(node('p', request.reason)); list($('candidate-summary'), request.items);
      put('report-note', '이 사례에는 계산 결과나 SHACL 실행 기록이 없습니다. 아래 확인 요청은 원자료를 읽고 연구자가 작성했습니다. 원자료가 틀렸다고 판정하지 않습니다.');
      put('disposition', '확인 요청 · 변경 미실행'); put('disposition-label', '');
      $('decision-summary').append(node('h3', '허용하지 않는 자동 처리')); list($('decision-summary'), request.forbidden);
      ['candidate-json','output-json','evaluation-json','before-conforms','after-conforms','before-json','after-json'].forEach(id => put(id, ''));
      $('evaluation-summary').replaceChildren();
    } else {
      const result = c.outputs[`${$('arm-select').value}|${$('postcheck-select').value}`];
      put('candidate-title', '후보와 근거'); put('report-title', '변경 전후 점검'); put('decision-title', '저장된 판단');
      put('candidate-json', json({candidate_reference_ids: result.candidate_reference_ids, candidate_citations: result.candidate_citations, candidate_patch: result.candidate_patch}));
      table($('candidate-summary'), {candidate_reference_ids: result.candidate_reference_ids, candidate_citations: result.candidate_citations, candidate_patch: result.candidate_patch});
      put('report-note', '저장된 SHACL·Python 보고서입니다. 규칙 적합성은 사실의 진실성이나 근거의 완전성을 보장하지 않습니다.');
      report('before', result.before_report); report('after', result.after_report);
      put('disposition', result.disposition);
      put('disposition-label', {propose_patch: '수정안 제안', request_evidence: '추가 근거 요청', request_reconciliation: '자료 대조 요청'}[result.disposition] || '');
      table($('decision-summary'), {diff: result.diff, diagnostics: result.diagnostics});
      put('output-json', json(result)); put('evaluation-json', json(c.evaluation)); table($('evaluation-summary'), c.evaluation);
      if (c.paired_missing_case) $('evaluation-summary').append(node('p', `동일 입력 비교 사례: ${show(c.paired_missing_case)}`, 'small'));
    }
  }
  if (!data?.cases?.length) {
    put('playback-status', '저장된 데이터 파일을 읽지 못했습니다. data.js가 같은 폴더에 있는지 확인해 주세요.');
    ['case-select', 'arm-select', 'postcheck-select', 'replay'].forEach(id => { $(id).disabled = true; });
    return;
  }
  options('case-select', data.cases); options('arm-select', data.arms); options('postcheck-select', data.postchecks);
  $('arm-select').value = 'SHACL_AF_relation_candidate';
  $('postcheck-select').value = 'shadow_revalidation';
  put('global-provenance', json(data.provenance));
  const attribution = data.source_attribution;
  put('attribution-json', json(attribution));
  function sourceLink(label, url) {
    if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) return node('span', label);
    const a = node('a', label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  }
  $('attribution').append(sourceLink(attribution.title, attribution.url),
    node('p', attribution.authors.join(' · ')), sourceLink(attribution.license, attribution.license_url));
  ['case-select','arm-select','postcheck-select'].forEach(id => $(id).addEventListener('change', render));
  $('replay').addEventListener('click', () => {
    if (timers.length) { cancelPlayback(true); return; }
    cancelPlayback();
    if (motion.matches) {
      stages.forEach(id => $(id).classList.add('active'));
      put('playback-status', '동작 줄이기 설정에 따라 모든 단계를 한 번에 강조합니다. 저장된 기록은 변경되지 않습니다.'); return;
    }
    $('replay').textContent = '흐름 강조 중지';
    const highlight = index => {
      stages.forEach((id, i) => $(id).classList.toggle('active', i === index));
      put('playback-status', `${index + 1}/5 · ${stageLabels[index]} · 저장된 기록 강조`);
    };
    highlight(0);
    for (let index = 1; index < stages.length; index++) timers.push(setTimeout(() => highlight(index), index * 1000));
    timers.push(setTimeout(() => { cancelPlayback(); put('playback-status', '흐름 강조를 마쳤습니다. 저장된 기록은 변경되지 않았습니다.'); }, 5000));
  });
  motion.addEventListener('change', () => cancelPlayback(true));
  window.addEventListener('pagehide', () => cancelPlayback());
  render();
})();
