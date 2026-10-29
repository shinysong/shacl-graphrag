"""Create and execute the self-contained seminar lab; never runs research campaigns."""
from pathlib import Path
import argparse
import ast
import json
import hashlib
import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/seminar_manufacturing_examples.py'
DEFAULT = ROOT / 'docs/experiments/seminar/notebooks/manufacturing-shacl.ipynb'


def build(output):
    constants = {}
    for node in ast.parse(RUNNER.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {'PREFIX', 'DATA', 'SCHEMA', 'MANUFACTURER_SHAPE'}:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
    cells = []
    def md(text):
        cells.append(nbf.v4.new_markdown_cell(text))
    def code(key, text):
        cell = nbf.v4.new_code_cell(text)
        cell['id'] = key
        cells.append(cell)
    md('''# 제조 부품 RDF와 SHACL 실습

P1의 제조사 기록을 검사하고 결과를 읽는 작은 예제입니다. 데이터와 Shape를 이 파일에 담아 저장소 없이 실행할 수 있습니다. 모든 코드 셀은 위에서 아래로 실행하세요. 저장된 출력은 실제 Python 커널에서 실행한 결과입니다.

발표 HTML의 ▶는 이 노트북의 저장 출력을 보여 줍니다. 직접 코드를 바꿔 실행하려면 이 노트북을 사용하세요.

## 실행 준비

Python 3.11 이상과 uv를 준비한 뒤 노트북을 저장한 폴더에서 실행합니다.

```bash
uv run --with jupyterlab --with ipykernel --with rdflib==7.6.0 --with pyshacl==0.40.1 --with owlrl==7.6.2 jupyter lab manufacturing-shacl.ipynb
```

API 키나 외부 데이터 다운로드는 필요하지 않습니다. 첫 환경 구성에는 패키지 다운로드가 필요합니다. 아래 예제는 학습용 합성 데이터이며 연구 벤치마크가 아닙니다.''')
    code('setup', '''from rdflib import Graph, Namespace, RDF
from pyshacl import validate
from owlrl import DeductiveClosure, OWLRL_Semantics
from importlib.metadata import version

EX = Namespace("https://example.org/manufacturing/")
SH = Namespace("http://www.w3.org/ns/shacl#")
''' + 'PREFIX = ' + repr(constants['PREFIX']) + '\n' + 'SCHEMA = ' + repr(constants['SCHEMA']) + '\n' + '''for package in ("rdflib", "pyshacl", "owlrl"):
    print(f"{package}: {version(package)}")''')
    md('## 1. 검사할 데이터와 Shape\n\nP1은 볼트이며 A1에 장착됩니다. 이 입력에는 제조사 기록이 없습니다. Shape는 P1의 제조사 값이 하나 이상이며 IRI인지 검사합니다. `PREFIX`와 `SCHEMA`는 앞 셀에서 준비했습니다.')
    code('data', 'DATA = """' + constants['DATA'] + '"""\n' + '''data = Graph().parse(data=PREFIX + DATA, format="turtle")
print(f"데이터: {len(data)}개 트리플")''')
    # Keep the exact executable teaching Shape, including its comments.
    code('shape', 'SHAPE = """' + constants['MANUFACTURER_SHAPE'] + '"""\n' + '''shapes = Graph().parse(data=PREFIX + SHAPE, format="turtle")
print(f"Shape: {len(shapes)}개 트리플")''')
    md('## 2. pySHACL 실행\n\n`validate()`는 적합 여부, RDF 보고서, 텍스트 보고서를 반환합니다. `inference="none"`으로 추론 없이 현재 데이터만 검사합니다.')
    code('validate', '''conforms, report, report_text = validate(
    data, shacl_graph=shapes, inference="none")
print("conforms =", bool(conforms))''')
    code('report', '''for result in report.subjects(RDF.type, SH.ValidationResult):
    print("대상:", report.value(result, SH.focusNode).n3(data.namespace_manager))
    print("속성:", report.value(result, SH.resultPath).n3(data.namespace_manager))
    print("조건:", str(report.value(result, SH.sourceConstraintComponent)).split("#")[-1])
    print("메시지:", report.value(result, SH.resultMessage))''')
    md('`conforms=False`이므로 실행한 조건을 충족하지 못했습니다. 보고서를 보면 P1의 제조사 필수 값이 빠졌습니다. 아래 두 셀은 같은 보고서의 텍스트와 RDF 표현입니다.')
    code('full-text', 'print(report_text)')
    code('rdf-report', 'print(report.serialize(format="turtle"))')
    md('## 3. 제조사 값을 추가한 뒤 다시 검사\n\n원본을 복사해 제조사 IRI를 추가합니다. `MakerA`는 학습용 식별자입니다. 검증 통과와 실제 제조사 확인은 별개입니다.')
    code('repair', '''complete = Graph()
for triple in data:
    complete.add(triple)
complete.add((EX.P1, EX.manufacturer, EX.MakerA))
conforms_after, _, _ = validate(complete, shacl_graph=shapes, inference="none")
print("제조사 추가 후 conforms =", bool(conforms_after))
assert not conforms and conforms_after''')
    md('## 4. 추론으로 추가되는 관계\n\n기록에는 P1의 Bolt 타입과 A1 장착 관계만 있습니다. 클래스 계층과 역관계 정의를 적용하면 Component 타입과 역방향 hasPart 관계를 조회할 수 있습니다.')
    code('reasoning', '''asserted = Graph().parse(data=PREFIX + DATA + "\\n" + SCHEMA, format="turtle")
expanded = Graph()
for triple in asserted:
    expanded.add(triple)
DeductiveClosure(OWLRL_Semantics).expand(expanded)
for label, triple in [
    ("P1 a Component", (EX.P1, RDF.type, EX.Component)),
    ("A1 hasPart P1", (EX.A1, EX.hasPart, EX.P1)),
]:
    print(f"{label}: 원본={triple in asserted}, 추론 후={triple in expanded}")''')
    md('''## 직접 바꿔 볼 내용

- 제조사를 IRI 대신 문자열로 넣으면 어떤 위반이 나오는가?
- `sh:minCount 1`을 제거하면 제조사 누락 결과는 어떻게 달라지는가?
- `owl:inverseOf` 정의를 빼면 역관계가 도출되는가?

공식 문서: [pySHACL](https://github.com/RDFLib/pySHACL), [SHACL](https://www.w3.org/TR/shacl/), [OWL-RL 구현](https://owl-rl.readthedocs.io/en/latest/owlrl.html).

실행 기록은 이 파일의 셀 출력과 `execution_count`에 저장됩니다. HTML 발표의 코드와 결과는 이 노트북에서 가져옵니다.''')
    nb = nbf.v4.new_notebook(cells=cells, metadata={
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'seminar': {'teaching_runner_sha256': hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
                    'builder_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'scope': 'self-contained synthetic teaching notebook; no API calls'},
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    # Execute in the notebook folder to prove no repository imports/data files are needed.
    try:
        NotebookClient(nb, timeout=60, kernel_name='python3',
                       resources={'metadata': {'path': str(output.parent)}}).execute()
    except Exception:
        nbf.write(nb, output.with_suffix('.failed.ipynb'))
        raise
    nbf.validate(nb)
    nbf.write(nb, output)
    print(json.dumps({'notebook': str(output), 'code_cells': sum(c.cell_type == 'code' for c in nb.cells),
                      'executed': True, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT)
    build(parser.parse_args().output)
