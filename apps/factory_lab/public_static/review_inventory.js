/* Standalone review inventory; deliberately owns no persistence or approval logic.
 * window.ReviewInventory.create(options) -> { element, update(patch), destroy() }
 * options.entries: [{id, kind, sourceLabel, column, samples: string[], meaning,
 *   target: string, status, unsaved?: boolean}]. IDs must be unique strings.
 * options.statusLabels / kindLabels: optional dictionaries of display labels.
 * options.showKindFilter: optional boolean (default: show for multiple kinds).
 * options.allowBulk: boolean; options.mutable: boolean or () => boolean.
 * options.onOpen(id): opens the host editor (also available when read-only).
 * options.onApprove(ids): asks the host to preview selected approvals; never saves.
 * update() accepts the same options, clears selection and preserves valid filters
 * and the current page. destroy() removes the element and releases row data.
 */
(function (global) {
  'use strict';
  let sequence = 0;
  const defaults = {pending: '미승인 · 검토 대기', approved: '승인', insufficient: '미승인 · 근거 부족', excluded: '제외'};
  const defaultKinds = {mapping: '필드', field: '필드', policy: '정책', relation: '관계'};
  const text = value => value == null ? '' : String(value);
  function node(tag, content, className) {
    const result = document.createElement(tag);
    if (content !== undefined) result.textContent = text(content);
    if (className) result.className = className;
    return result;
  }
  function create(initial) {
    let options = {...initial}, entries = [], page = 0, destroyed = false;
    const selected = new Set(), pageSize = 20, uid = `review-inventory-${++sequence}`;
    const element = node('section', undefined, 'review-inventory');
    element.setAttribute('aria-label', '자료 의미 검토 목록');
    const summary = node('p', undefined, 'review-inventory-summary');
    const filters = node('div', undefined, 'review-inventory-filters');
    const search = node('input');
    search.type = 'search';
    search.placeholder = '자료·열·의미·값 검색';
    const source = node('select'), status = node('select'), kind = node('select');
    function labelled(label, control, suffix) {
      control.id = `${uid}-${suffix}`;
      const wrapper = node('label', label);
      wrapper.htmlFor = control.id;
      wrapper.append(control);
      return wrapper;
    }
    const kindField = labelled('종류', kind, 'kind');
    filters.append(labelled('검색', search, 'search'), labelled('자료', source, 'source'), labelled('상태', status, 'status'), kindField);
    const selection = node('div', undefined, 'review-inventory-selection');
    const selectedCount = node('span');
    selectedCount.setAttribute('role', 'status');
    const approve = node('button');
    approve.type = 'button';
    const clear = node('button', '선택 해제');
    clear.type = 'button';
    selection.append(selectedCount, approve, clear);
    const results = node('p', undefined, 'review-inventory-results');
    results.id = `${uid}-results`;
    results.setAttribute('role', 'status');
    const scroll = node('div', undefined, 'review-inventory-scroll');
    scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region');
    scroll.setAttribute('aria-label', '자료 의미 검토 표 · 가로로 스크롤할 수 있습니다');
    scroll.setAttribute('aria-describedby', results.id);
    const table = node('table');
    const caption = node('caption', '자료별 열·원본 예시·업무 의미와 검토 상태');
    const head = node('thead'), header = node('tr'), body = node('tbody');
    const selectAll = node('input');
    selectAll.type = 'checkbox';
    selectAll.setAttribute('aria-label', '현재 페이지에서 승인 가능한 필드 모두 선택');
    const selectionHeader = node('th');
    selectionHeader.scope = 'col';
    selectionHeader.append(selectAll);
    header.append(selectionHeader);
    for (const label of ['종류', '자료', '열·항목', '원본 예시', '업무 의미', '표준 필드·적용 대상', '상태', '검토']) {
      const cell = node('th', label);
      cell.scope = 'col';
      header.append(cell);
    }
    head.append(header);
    table.append(caption, head, body);
    scroll.append(table);
    const navigation = node('nav', undefined, 'review-inventory-pagination');
    navigation.setAttribute('aria-label', '검토 목록 페이지');
    const previous = node('button', '이전'), next = node('button', '다음'), pageLabel = node('span');
    previous.type = next.type = 'button';
    navigation.append(previous, pageLabel, next);
    element.append(summary, filters, selection, results, scroll, navigation);
    let visible = [], checkboxes = [];
    const mutable = () => typeof options.mutable === 'function' ? Boolean(options.mutable()) : options.mutable !== false;
    const eligible = entry => Boolean(options.allowBulk) && mutable() && ['mapping', 'field'].includes(entry.kind) && !['approved', 'excluded'].includes(entry.status);
    const labels = () => ({...defaults, ...options.statusLabels});
    function fillSelect(control, values, allLabel) {
      const previousValue = control.value;
      control.replaceChildren();
      for (const [value, label] of [['', allLabel], ...values]) {
        const item = node('option', label);
        item.value = value;
        control.append(item);
      }
      control.value = values.some(([value]) => value === previousValue) ? previousValue : '';
    }
    function updateSelection() {
      selectedCount.textContent = `선택 ${selected.size}개`;
      approve.textContent = `선택한 ${selected.size}개 승인 미리보기`;
      approve.disabled = !mutable() || !selected.size || typeof options.onApprove !== 'function';
      clear.disabled = !selected.size;
      const available = visible.filter(eligible);
      const count = available.filter(entry => selected.has(entry.id)).length;
      selectAll.disabled = !available.length;
      selectAll.checked = available.length > 0 && count === available.length;
      selectAll.indeterminate = count > 0 && count < available.length;
      for (const [entry, checkbox] of checkboxes) checkbox.checked = selected.has(entry.id);
    }
    function redraw() {
      if (destroyed) return;
      const query = search.value.trim().toLocaleLowerCase();
      const matches = entries.filter(entry => (!source.value || entry.sourceLabel === source.value) && (!status.value || entry.status === status.value) && (!kind.value || entry.kind === kind.value) && (!query || [entry.sourceLabel, entry.column, entry.meaning, entry.target, ...entry.samples].join(' ').toLocaleLowerCase().includes(query)));
      const pages = Math.max(1, Math.ceil(matches.length / pageSize));
      page = Math.min(page, pages - 1);
      visible = matches.slice(page * pageSize, (page + 1) * pageSize);
      results.textContent = matches.length ? `검색 결과 ${matches.length}개 · ${page * pageSize + 1}–${page * pageSize + visible.length}개 표시` : '조건에 맞는 항목이 없습니다.';
      body.replaceChildren();
      checkboxes = [];
      const kindLabels = {...defaultKinds, ...options.kindLabels};
      for (const entry of visible) {
        const row = node('tr');
        row.dataset.reviewId = entry.id;
        const selectCell = node('td'), checkbox = node('input');
        checkbox.type = 'checkbox';
        checkbox.disabled = !eligible(entry);
        checkbox.setAttribute('aria-label', `${entry.sourceLabel} · ${entry.column || kindLabels[entry.kind] || entry.kind} 선택`);
        checkbox.addEventListener('change', () => {
          if (eligible(entry) && checkbox.checked) selected.add(entry.id);
          else selected.delete(entry.id);
          updateSelection();
        });
        selectCell.append(checkbox);
        checkboxes.push([entry, checkbox]);
        row.append(selectCell);
        for (const value of [kindLabels[entry.kind] || entry.kind, entry.sourceLabel || '자료 정보 없음', entry.column || '항목 정보 없음']) row.append(node('td', value));
        const samples = node('td', entry.samples.length ? entry.samples.slice(0, 3).map(value => value === '' ? '(빈 값)' : value).join(' / ') : '값 없음');
        samples.title = entry.samples.map(value => value === '' ? '(빈 값)' : value).join(' / ') || '값 없음';
        row.append(samples, node('td', entry.meaning || '의미 확인 필요'), node('td', entry.target || '미지정'));
        const stateCell = node('td', labels()[entry.status] || entry.status || '미승인 · 상태 확인 필요');
        if (entry.unsaved) stateCell.append(node('span', ' · 미저장', 'review-inventory-unsaved'));
        const actionCell = node('td'), open = node('button', '검토·수정');
        open.type = 'button';
        open.setAttribute('aria-label', `${entry.sourceLabel} · ${entry.column || kindLabels[entry.kind] || entry.kind} 검토·수정`);
        open.disabled = typeof options.onOpen !== 'function';
        open.addEventListener('click', () => { if (!destroyed && typeof options.onOpen === 'function') options.onOpen(entry.id); });
        actionCell.append(open);
        row.append(stateCell, actionCell);
        body.append(row);
      }
      if (!visible.length) {
        const empty = node('td', entries.length ? '검색어나 필터를 바꿔 확인하세요.' : '검토할 항목이 없습니다.');
        empty.colSpan = 9;
        const row = node('tr');
        row.append(empty);
        body.append(row);
      }
      pageLabel.textContent = `${page + 1} / ${pages} 페이지`;
      previous.disabled = page === 0;
      next.disabled = page >= pages - 1;
      selection.hidden = !options.allowBulk;
      updateSelection();
    }
    function resetView() { selected.clear(); page = 0; redraw(); }
    search.addEventListener('input', resetView);
    for (const control of [source, status, kind]) control.addEventListener('change', resetView);
    previous.addEventListener('click', () => { selected.clear(); page = Math.max(0, page - 1); redraw(); });
    next.addEventListener('click', () => { selected.clear(); page += 1; redraw(); });
    clear.addEventListener('click', () => { selected.clear(); updateSelection(); });
    selectAll.addEventListener('change', () => {
      for (const entry of visible.filter(eligible)) {
        if (selectAll.checked) selected.add(entry.id);
        else selected.delete(entry.id);
      }
      updateSelection();
    });
    approve.addEventListener('click', () => {
      const ids = visible.filter(entry => selected.has(entry.id) && eligible(entry)).map(entry => entry.id);
      if (!destroyed && ids.length && typeof options.onApprove === 'function') options.onApprove(ids);
    });
    function update(patch) {
      if (destroyed) return;
      options = {...options, ...patch};
      const seen = new Set();
      entries = (Array.isArray(options.entries) ? options.entries : []).filter(entry => entry && typeof entry.id === 'string' && !seen.has(entry.id) && seen.add(entry.id)).map(entry => ({...entry, kind: text(entry.kind), sourceLabel: text(entry.sourceLabel), column: text(entry.column), meaning: text(entry.meaning), target: text(entry.target), status: text(entry.status), samples: Array.isArray(entry.samples) ? entry.samples.map(text) : []}));
      selected.clear();
      const approved = entries.filter(entry => entry.status === 'approved').length;
      const excluded = entries.filter(entry => entry.status === 'excluded').length;
      summary.textContent = `전체 ${entries.length}개 · 승인 ${approved}개 · 미승인 ${entries.length - approved - excluded}개 · 제외 ${excluded}개`;
      fillSelect(source, [...new Set(entries.map(entry => entry.sourceLabel))].filter(Boolean).map(value => [value, value]), '모든 자료');
      const statusLabels = labels();
      fillSelect(status, [...new Set(entries.map(entry => entry.status))].filter(Boolean).map(value => [value, statusLabels[value] || value]), '모든 상태');
      const kinds = [...new Set(entries.map(entry => entry.kind))].filter(Boolean), kindLabels = {...defaultKinds, ...options.kindLabels};
      fillSelect(kind, kinds.map(value => [value, kindLabels[value] || value]), '모든 종류');
      kindField.hidden = options.showKindFilter === false || (options.showKindFilter !== true && kinds.length < 2);
      if (kindField.hidden) kind.value = '';
      redraw();
    }
    update({});
    return {element, update, destroy() { destroyed = true; selected.clear(); entries = []; visible = []; checkboxes = []; options = {}; element.replaceChildren(); element.remove(); }};
  }
  global.ReviewInventory = Object.freeze({create});
})(window);
