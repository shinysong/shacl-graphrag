"""Local, human-reviewed document-to-SHACL workbench. Explicit optional LLM calls."""
from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from rule_workbench.connectors import list_db_tables, read_db_table, read_file
from rule_workbench.core import demo_project, fingerprint, new_project, run_checks, validate_project
from rule_workbench.exports import export_bundle, export_excel, export_json, import_json
from rule_workbench.extractors import candidate_rules, extract_document
from rule_workbench.llm import build_prompt
from rule_workbench.transport import available_models, budget_status, generate_candidates

st.set_page_config(page_title="규칙 검토실", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container {max-width:1320px;padding-top:2.3rem;padding-bottom:4rem;}
[data-testid="stSidebar"] {border-right:1px solid #8b98a333;}
[data-testid="stMetric"] {border:1px solid #8b98a344;border-radius:12px;padding:12px 18px;}
h1 {letter-spacing:-.045em;} h2,h3 {letter-spacing:-.025em;}
[data-testid="stCaptionContainer"] {line-height:1.7;}
.stButton button,.stDownloadButton button {border-radius:8px;}
@media (max-width:640px) {
  h1 {font-size:1.85rem!important;line-height:1.25!important;word-break:keep-all;}
  .block-container {padding-top:1.5rem;}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {flex-direction:row!important;flex-wrap:wrap!important;gap:.5rem!important;}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {flex:1 1 calc(50% - .5rem)!important;min-width:calc(50% - .5rem)!important;}
  [data-testid="stMetric"] {padding:8px 12px;}
}
</style>""", unsafe_allow_html=True)

if "project" not in st.session_state:
    st.session_state.project = new_project()
    st.session_state.result = None
    st.session_state.epoch = 0


def replace_project(project):
    st.session_state.project = validate_project(project)
    st.session_state.result = None
    st.session_state.previous_result = None
    st.session_state.epoch += 1
    st.rerun()


def save_project(project):
    st.session_state.project = validate_project(project)
    st.rerun()


def label(table):
    source = table.get("source", {})
    origin = source.get("sheet") or source.get("table") or source.get("file") or source.get("kind", "")
    return f'{table["name"]} · {origin} · {len(table["rows"]):,}행'


def add_tables(tables):
    project = copy.deepcopy(st.session_state.project)
    names = {t["name"] for t in project["tables"]}
    for table in tables:
        base = table["name"]
        index = 2
        while table["name"] in names:
            table["name"] = f"{base} ({index})"
            index += 1
        names.add(table["name"])
        project["tables"].append(table)
    save_project(project)


def report_error(exc):
    # Connector errors are intentionally generic here: credentials never enter UI output.
    st.error(f"작업을 완료하지 못했습니다. {exc}" if isinstance(exc, ValueError) else "작업을 완료하지 못했습니다. 파일 형식과 입력 설정을 확인해 주세요.")


with st.sidebar:
    st.markdown("### ◈ 규칙 검토실")
    st.caption("LOCAL WORKBENCH · 로컬 프로토타입")
    with st.form("project_name_form"):
        project_name = st.text_input("작업 이름", value=st.session_state.project["name"], key=f"name_{st.session_state.epoch}")
        if st.form_submit_button("이름 저장"):
            project = copy.deepcopy(st.session_state.project)
            project["name"] = project_name.strip() or "규칙 검토 작업"
            save_project(project)
    st.divider()
    st.caption("샘플 데이터는 아래 버튼을 누를 때만 불러옵니다. 현재 작업을 교체합니다.")
    if st.button("예제 프로젝트 불러오기", width="stretch"):
        replace_project(demo_project())
    imported = st.file_uploader("프로젝트 JSON 가져오기", max_upload_size=20, type=["json"], key="project_import")
    if st.button("JSON으로 현재 작업 교체", disabled=imported is None, width="stretch"):
        try:
            replace_project(import_json(imported.getvalue()))
        except Exception as exc:
            report_error(exc)
    st.divider()
    st.caption("데이터 연결 → 문서에서 후보 추출 → 사람이 규칙 확정 → SHACL 검사")
    st.caption("기본 모드는 로컬에서 실행합니다. LLM 모드는 실행 버튼을 누를 때만 외부 API를 호출합니다. 검사 통과는 원본 사실의 진실성이나 문서 해석의 정확성을 보증하지 않습니다.")

project = st.session_state.project
result = st.session_state.get("result")
fresh = result is not None and result.get("fingerprint") == fingerprint(project)
epoch = st.session_state.epoch

st.caption("DOCUMENT → RULE → DATA")
st.title("데이터와 규칙을 한곳에서 검토하세요")
st.write("원본 표를 연결하고 문서의 규칙 후보를 확인한 뒤, 열에 연결한 규칙으로 실제 데이터를 검사합니다.")
a, b, c, d = st.columns(4)
a.metric("연결된 표", len(project["tables"]))
b.metric("데이터 행", f'{sum(len(t["rows"]) for t in project["tables"]):,}')
c.metric("확정 규칙", sum(r["status"] == "confirmed" for r in project["rules"]))
d.metric("검사 상태", "최신" if fresh else "다시 검사 필요" if result else "미실행")

connect_tab, document_tab, rule_tab, result_tab, export_tab = st.tabs(["데이터 연결", "규칙 문서", "규칙 검토", "검사 결과", "내보내기"])

with connect_tab:
    st.subheader("검사할 데이터")
    st.caption("CSV · Excel의 모든 시트 · SQLite의 모든 테이블을 읽습니다. 표마다 최대 5,000행을 읽으며, 잘린 데이터는 별도로 표시합니다.")
    uploads = st.file_uploader("데이터 파일", max_upload_size=20, type=["csv", "xlsx", "db", "sqlite", "sqlite3"], accept_multiple_files=True)
    if st.button("선택한 데이터 추가", disabled=not uploads, type="primary"):
        try:
            tables = []
            for upload in uploads:
                tables.extend(read_file(upload.name, upload.getvalue()))
            add_tables(tables)
        except Exception as exc:
            report_error(exc)
    with st.expander("PostgreSQL 읽기 전용 연결"):
        st.caption("연결 문자열은 현재 세션의 메모리에만 둡니다. 프로젝트 파일에는 저장하지 않습니다. 임의 SQL은 실행하지 않습니다.")
        if st.button("연결 정보 지우기"):
            st.session_state.pop("database_url", None)
            st.session_state.pop("database_tables", None)
            st.session_state.pop("database_bound_url", None)
            st.rerun()
        url = st.text_input("PostgreSQL 연결 문자열", type="password", key="database_url", placeholder="postgresql+psycopg://user:password@host/database")
        if st.button("테이블 목록 조회", disabled=not url):
            try:
                st.session_state.database_tables = list_db_tables(url)
                st.session_state.database_bound_url = url
            except Exception:
                st.error("연결하지 못했습니다. 연결 주소, 권한, 네트워크 설정을 확인해 주세요.")
        db_tables = st.session_state.get("database_tables", []) if st.session_state.get("database_bound_url") == url else []
        if db_tables:
            table_name = st.selectbox("가져올 테이블", db_tables)
            if st.button("선택한 DB 테이블 추가"):
                try:
                    add_tables([read_db_table(url, table_name)])
                except Exception:
                    st.error("테이블을 읽지 못했습니다. 연결과 읽기 권한을 확인해 주세요.")
    if project["tables"]:
        selected = st.selectbox("원본 데이터 미리보기", range(len(project["tables"])), format_func=lambda i: label(project["tables"][i]), key=f"preview_{epoch}")
        table = project["tables"][selected]
        if table.get("source", {}).get("data_omitted"):
            st.info("원본 행을 제외한 작업 파일입니다. 데이터를 추가하고 규칙의 대상 표를 다시 연결하세요.")
        if table.get("source", {}).get("truncated"):
            st.warning("이 표는 5,000행까지만 가져왔습니다. 검사 결과는 가져온 범위에만 해당합니다.")
        st.dataframe(table["rows"], width="stretch")
        st.caption(f'원본 열 {len(table["columns"])}개 · 표시된 행 순서가 검사 결과의 데이터 행 번호입니다.')
        with st.expander("데이터 출처"):
            st.json(table.get("source", {}))
    else:
        st.info("파일을 추가하거나 왼쪽에서 예제 프로젝트를 불러오세요.")

with document_tab:
    st.subheader("규칙의 근거 문서")
    st.caption("PDF의 텍스트와 Markdown을 읽습니다. OCR은 지원하지 않습니다. 후보는 사람이 확인하기 전까지 초안입니다.")
    mode = st.radio("후보 추출 방식", ["기본 문장 후보", "LLM 규칙·연결 제안"], horizontal=True)
    selected_docs = st.multiselect("기존 문서 선택", range(len(project["documents"])), format_func=lambda i: f'{i + 1}. {project["documents"][i]["name"]}', key=f"documents_{epoch}")
    documents = st.file_uploader("PDF 또는 Markdown", max_upload_size=20, type=["pdf", "md", "markdown"], accept_multiple_files=True)
    manual = st.text_area("직접 입력할 규칙 문서", placeholder="예: 제품 코드는 반드시 입력해야 한다.\n납기일은 주문일보다 빠를 수 없다.")
    new_documents = []
    document_error = False
    try:
        new_documents = [extract_document(f.name, f.getvalue()) for f in documents or []]
        if manual.strip():
            new_documents.append(extract_document("직접 입력.md", manual.encode("utf-8")))
    except Exception as exc:
        document_error = True
        report_error(exc)
    chosen_documents = [project["documents"][i] for i in selected_docs] + new_documents
    if mode == "기본 문장 후보":
        if st.button("문서 추가 및 후보 추출", disabled=document_error or not chosen_documents):
            try:
                updated = copy.deepcopy(project)
                for document in new_documents:
                    if document not in updated["documents"]:
                        updated["documents"].append(document)
                for document in chosen_documents:
                    updated["rules"].extend(candidate_rules(document))
                save_project(updated)
            except Exception as exc:
                report_error(exc)
        st.caption("문서당 후보는 최대 100개, 작업 전체 규칙은 최대 100개입니다. 기본 후보는 문장 단위이며 의미 해석을 수행하지 않습니다.")
    else:
        st.caption("실행하면 선택한 문서 내용과 연결된 표 이름·ID·열 이름을 OpenRouter로 보냅니다. 데이터 행, 기존 규칙, DB 연결 정보는 보내지 않습니다. 요청과 응답은 서버에 기록됩니다.")
        models, budget = [], {}
        try:
            models = available_models()
            budget = budget_status()
        except Exception:
            st.error("LLM 설정을 읽지 못했습니다. 서버 설정을 확인해 주세요.")
        if budget:
            st.caption(f'호출 {budget.get("attempts", 0)}/{budget.get("max_calls", 0)} · 예약 비용 ${budget.get("reserved_usd", 0)} / ${budget.get("max_usd", 0)} · 기한 {budget.get("deadline_utc", "미설정")}')
        model = st.selectbox("LLM 모델", models, disabled=not models)
        if not models or not budget.get("configured"):
            st.info("서버에서 모델과 실행 예산을 설정해야 LLM 제안을 사용할 수 있습니다.")
        prompt_valid = False
        if chosen_documents and not document_error:
            try:
                prompt = build_prompt(project, chosen_documents)
                prompt_valid = True
                with st.expander("전송할 전체 프롬프트 확인"):
                    st.text(prompt["system_prompt"])
                    st.text(prompt["user_prompt"])
            except Exception as exc:
                report_error(exc)
        if len(project["rules"]) >= 100:
            st.warning("작업당 규칙 한도는 100개입니다. 후보를 추가하려면 기존 규칙을 정리하세요.")
        if st.button("LLM 규칙·연결 제안 실행", type="primary", disabled=not prompt_valid or not model or not budget.get("configured") or len(project["rules"]) >= 100):
            try:
                with st.spinner("문서의 규칙과 열 연결 후보를 요청하고 있습니다…"):
                    response = generate_candidates(project, chosen_documents, model)
                applied_key = f"llm_applied_{epoch}"
                applied = set(st.session_state.get(applied_key, []))
                request_id = response["request_id"]
                st.session_state[f"llm_response_{epoch}"] = response
                if request_id not in applied:
                    updated = copy.deepcopy(project)
                    for document in new_documents:
                        if document not in updated["documents"]:
                            updated["documents"].append(document)
                    updated["rules"].extend({**copy.deepcopy(rule), "status": "draft"} for rule in response["rules"])
                    validated = validate_project(updated)
                    applied.add(request_id)
                    st.session_state[applied_key] = list(applied)
                    save_project(validated)
                else:
                    st.info("이 요청의 후보는 이미 현재 작업에 추가했습니다. 중복 추가하지 않습니다.")
            except Exception:
                st.error("LLM 후보를 추가하지 못했습니다. 입력 한도·규칙 100개 한도·서버 실행 기록을 확인해 주세요. 자동 재시도는 하지 않습니다.")
        response = st.session_state.get(f"llm_response_{epoch}")
        if response:
            st.caption(f'모델 {response["model"]} · 요청 {response["request_id"]} · 보고 비용 ${response.get("cost_usd", "미확인")}')
            if response.get("cached"):
                st.info("저장된 응답을 재사용했습니다. 추가 API 호출은 없습니다.")
            for note in response.get("notes", []):
                st.write(note)
            for candidate in response.get("rules", []):
                if candidate.get("kind") == "unsupported":
                    st.warning(f'지원하지 않는 조건 · {candidate["text"]}')
                for question in candidate.get("llm", {}).get("questions", []):
                    st.write(f'확인 필요 · {question}')
    for index, document in enumerate(project["documents"]):
        with st.expander(document["name"], expanded=len(project["documents"]) == 1):
            for segment in document["segments"]:
                location = f'{segment["page"]}쪽' if segment.get("page") else f'{segment.get("line", "")}행'
                st.caption(location)
                st.text(segment["text"])
    if project["rules"]:
        st.dataframe([{ "규칙": r["text"], "상태": "확정" if r["status"] == "confirmed" else "초안", "출처": r.get("source", {}).get("file", "") } for r in project["rules"]], width="stretch", hide_index=True)

with rule_tab:
    st.subheader("규칙 해석과 열 연결")
    st.caption("원문과 연결할 열, 검사 조건을 확인한 뒤 확정하세요. 기본 문장 후보의 유형은 ‘필수값’입니다. LLM 제안도 원문과 비교하고 실제 의미에 맞게 수정해야 합니다.")
    if st.button("빈 규칙 추가"):
        updated = copy.deepcopy(project)
        updated["rules"].append({"id": uuid4().hex, "text": "새 규칙", "source": {"file": "직접 작성", "quote": ""}, "status": "draft", "table": "", "column": "", "kind": "required", "params": {}})
        save_project(updated)
    if project["rules"]:
        rule_index = st.selectbox("검토할 규칙", range(len(project["rules"])), format_func=lambda i: f'{i + 1}. {project["rules"][i]["text"]}', key=f"rule_select_{epoch}")
        rule = project["rules"][rule_index]
        key = f'{epoch}_{rule["id"]}'
        with st.expander("보존된 원문과 위치", expanded=True):
            st.json(rule.get("source", {}))
        if rule.get("llm"):
            metadata = rule["llm"]
            st.caption(f'LLM 제안 · {metadata.get("model", "")} · 요청 {metadata.get("request_id", "")}')
            st.write(metadata.get("rationale", ""))
            for question in metadata.get("questions", []):
                st.warning(f"확인 필요 · {question}")
            st.caption("인용문 위치 대조 완료. 이 대조는 해석이나 조건의 정확성을 보증하지 않습니다." if metadata.get("source_verified") else "인용문 위치 대조 미확인")
        if rule["kind"] == "unsupported":
            st.warning("현재 검사 유형으로 표현할 수 없는 조건입니다. 지원되는 조건으로 바꾸기 전에는 자동 검사할 수 없습니다.")
        # Selectors are outside the form so dependent column/parameter controls update.
        names = [""] + [t["id"] for t in project["tables"]]
        table_labels = {t["id"]: label(t) for t in project["tables"]}
        table_name = st.selectbox("대상 표", names, index=names.index(rule["table"]) if rule["table"] in names else 0, format_func=lambda n: table_labels.get(n, "연결하지 않음"), key=f"map_table_{key}")
        table = next((t for t in project["tables"] if t["id"] == table_name), None)
        columns = [""] + (table["columns"] if table else [])
        column = st.selectbox("대상 열", columns, index=columns.index(rule["column"]) if rule["column"] in columns else 0, format_func=lambda n: n or "연결하지 않음", key=f"map_column_{key}_{table_name}")
        kinds = {"required": "필수값", "range": "숫자 범위", "allowed": "허용값 목록", "date_order": "날짜 순서 (대상 열 ≤ 비교 열)", "reference": "다른 표의 값 참조"}
        if rule["kind"] not in kinds:
            kinds[rule["kind"]] = f'미지원 유형: {rule["kind"]}'
        kind = st.selectbox("검사 유형", list(kinds), index=list(kinds).index(rule["kind"]), format_func=kinds.get, key=f"kind_{key}")
        target = ""
        if kind == "reference":
            target = st.selectbox("참조 대상 표", names, index=names.index(rule["params"].get("target_table")) if rule["params"].get("target_table") in names else 0, format_func=lambda n: table_labels.get(n, "연결하지 않음"), key=f"target_{key}")
        with st.form(f"edit_{key}_{kind}_{table_name}_{target}"):
            text = st.text_area("검사 규칙 설명", value=rule["text"])
            params = rule["params"] if rule["kind"] == kind else {}
            pending = {}
            if kind == "range":
                col1, col2 = st.columns(2)
                low = col1.text_input("최솟값 (빈칸: 제한 없음)", value="" if params.get("min") is None else str(params["min"]))
                high = col2.text_input("최댓값 (빈칸: 제한 없음)", value="" if params.get("max") is None else str(params["max"]))
            elif kind == "allowed":
                values = st.text_area("허용값 (한 줄에 하나)", value="\n".join(str(v) for v in params.get("values", [])))
                pending = {"values": [v.strip() for v in values.splitlines() if v.strip()]}
            elif kind == "date_order":
                other = st.selectbox("비교 날짜 열", columns, index=columns.index(params.get("other_column")) if params.get("other_column") in columns else 0)
                pending = {"other_column": other}
                st.caption("ISO 날짜를 비교합니다. 예: 주문일 ≤ 납기일")
            elif kind == "reference":
                target_table = next((t for t in project["tables"] if t["id"] == target), None)
                targets = [""] + (target_table["columns"] if target_table else [])
                target_column = st.selectbox("참조 대상 열", targets, index=targets.index(params.get("target_column")) if params.get("target_column") in targets else 0)
                pending = {"target_table": target, "target_column": target_column}
            confirmed = st.checkbox("원문 해석과 데이터 연결을 검토했으며 이 규칙을 확정합니다", value=rule["status"] == "confirmed")
            if st.form_submit_button("규칙 저장", type="primary"):
                try:
                    if kind == "range":
                        pending = {"min": str(Decimal(low)) if low.strip() else None, "max": str(Decimal(high)) if high.strip() else None}
                    updated = copy.deepcopy(project)
                    updated["rules"][rule_index].update(text=text, table=table_name, column=column, kind=kind, params=pending, status="confirmed" if confirmed else "draft")
                    save_project(updated)
                except Exception as exc:
                    report_error(exc)
        if st.button("이 규칙 삭제", key=f"delete_{key}"):
            updated = copy.deepcopy(project)
            del updated["rules"][rule_index]
            save_project(updated)
        st.caption("선택만 바꾼 내용은 아직 저장되지 않았습니다. ‘규칙 저장’ 후 검사를 실행하세요.")
    else:
        st.info("문서에서 후보를 추출하거나 빈 규칙을 추가하세요.")

with result_tab:
    st.subheader("원본 데이터 검사 결과")
    st.caption("한 번에 최대 20,000개 규칙×행 검사를 실행합니다. 저장된 규칙으로 RDF와 SHACL을 생성하고 pySHACL 검사를 실행합니다. 미확정 규칙이나 부족한 근거는 ‘판단 불가’로 남깁니다.")
    ready = st.checkbox("저장된 규칙과 현재 데이터로 검사를 실행하겠습니다", key=f"run_confirm_{epoch}")
    if st.button("검사 실행", type="primary", disabled=not ready):
        try:
            with st.spinner("규칙을 변환하고 데이터를 검사하고 있습니다…"):
                new_result = run_checks(project)
                st.session_state.previous_result = st.session_state.get("result")
                st.session_state.result = new_result
            st.rerun()
        except Exception as exc:
            report_error(exc)
    if result and not fresh:
        st.warning("마지막 검사 이후 작업이 바뀌었습니다. 이전 결과는 숨겼습니다. 다시 검사해 주세요.")
    elif fresh:
        previous = st.session_state.get("previous_result")
        if previous:
            prior = {(r["rule_id"], r["table"], r["row"]): r for r in previous["results"]}
            changes = []
            for item in result["results"]:
                old = prior.get((item["rule_id"], item["table"], item["row"]))
                if old is None or old["status"] != item["status"]:
                    changes.append({"규칙": item["rule_id"], "데이터 행": item["row"], "이전": old["status"] if old else "새 검사", "현재": item["status"]})
            with st.expander(f"직전 실행과 비교 · 변경 {len(changes)}건"):
                st.caption("같은 규칙 ID·테이블 ID·행 위치를 비교합니다. 데이터가 바뀌면 같은 업무 객체라는 보장은 없습니다. 제거된 검사는 아래에 별도 표시합니다.")
                st.dataframe(changes, hide_index=True)
                current_keys = {(r["rule_id"], r["table"], r["row"]) for r in result["results"]}
                removed = [r for k, r in prior.items() if k not in current_keys]
                if removed:
                    st.write(f"이번 실행에서 제외된 이전 검사: {len(removed)}건")
        statuses = {"pass": "통과", "violation": "위반", "unknown": "판단 불가", "not_applicable": "해당 없음"}
        metrics = st.columns(4)
        for col, (status, title) in zip(metrics, statuses.items()):
            col.metric(title, sum(r["status"] == status for r in result["results"]))
        st.caption("집계는 행별 검사 결과와 실행할 수 없는 규칙별 상태를 합친 건수입니다. 업체 수나 오류율이 아닙니다.")
        st.caption(f'{result.get("engine", "pySHACL")} · {result.get("created_at", "")} · 저장된 규칙과 데이터에 대한 결과')
        filters = st.multiselect("결과 상태", list(statuses), default=list(statuses), format_func=statuses.get)
        rows = [r for r in result["results"] if r["status"] in filters]
        st.dataframe([{"상태": statuses[r["status"]], "규칙": r["rule_text"], "표": next((t["name"] for t in project["tables"] if t["id"] == r["table"]), r["table"]), "데이터 행": r["row"], "설명": r["message"]} for r in rows], hide_index=True, width="stretch")
        if rows:
            picked = st.selectbox("원본 행 상세", range(len(rows)), format_func=lambda i: f'{statuses[rows[i]["status"]]} · {rows[i]["table"]} · {rows[i]["row"] or "—"}행 · {rows[i]["rule_text"]}')
            detail = rows[picked]
            st.write(detail["message"])
            st.json(detail.get("source", {}))
            table = next((t for t in project["tables"] if t["name"] == detail["table"] or t["id"] == detail["table"]), None)
            row_number = detail.get("row")
            if table and isinstance(row_number, int) and 1 <= row_number <= len(table["rows"]):
                st.dataframe([table["rows"][row_number - 1]], hide_index=True, width="stretch")
                st.caption("데이터 행 번호는 헤더를 제외한 1부터 시작합니다. 헤더가 첫 줄인 Excel에서는 시트 행 번호가 1만큼 더 큽니다.")
    elif not result:
        st.info("검사를 실행하면 규칙별 판정과 근거가 된 원본 행을 확인할 수 있습니다.")

with export_tab:
    st.subheader("검토 작업과 결과 저장")
    st.caption("JSON은 다시 가져올 수 있습니다. 기본값에서는 원본 행을 제외하며, 다시 검사하려면 데이터를 연결해야 합니다.")
    include_data = st.checkbox("원본 데이터 행과 문서 텍스트를 JSON·ZIP에 포함합니다", value=False)
    if result and not fresh:
        st.warning("이전 검사 결과는 현재 작업과 달라 내보내기에서 제외됩니다.")
    try:
        current_result = result if fresh else None
        a, b, c = st.columns(3)
        a.download_button("프로젝트 JSON", export_json(project, include_data=include_data), file_name="rules-project.json", mime="application/json", width="stretch")
        b.download_button("검토 보고서 Excel", export_excel(project, current_result), file_name="rules-report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        c.download_button("작업 묶음 ZIP", export_bundle(project, current_result, include_data=include_data), file_name="rules-workbench.zip", mime="application/zip", width="stretch")
        st.caption("보고서와 규칙에는 문서 인용이 포함됩니다. 검사 결과에는 판정 근거가 포함될 수 있으므로 공유 전에 확인하세요.")
        if fresh:
            st.download_button("SHACL 규칙 Turtle", result["shapes_ttl"], file_name="shapes.ttl", mime="text/turtle")
            if include_data:
                st.download_button("변환 데이터 Turtle", result["data_ttl"], file_name="data.ttl", mime="text/turtle")
    except Exception as exc:
        report_error(exc)
