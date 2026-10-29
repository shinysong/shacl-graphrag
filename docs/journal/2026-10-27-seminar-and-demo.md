# 제조 사례 중심 세미나와 실행 근거 데모

10월 26~27일에는 연구의 개념과 실행 결과를 설명하는 발표자료를 정리했습니다. 최종 자료는 흰 배경과 Pretendard 계열 글꼴을 사용한 45장 HTML·PDF입니다. 업무 질문에서 시작해 RDF·RDFS·OWL, 추론과 SHACL 검증, shape 작성, 실제 코드와 후속 연구 설계로 이어집니다.

## 개념 설명과 실제 실행의 구분

센서 대신 제조 부품을 예시로 사용하고 관계 그래프와 데이터 표를 함께 배치했습니다. 추론으로 얻은 결론, 데이터의 제약 충족, 현실의 사실 확인을 구분합니다. 일반 Python·SQL로도 같은 규칙을 구현할 수 있다는 점과 공유 스키마를 관리하려는 연구 의도를 설명합니다.

LLM 대화창과 도구 화면 중 설명용 그림은 실제 호출 결과와 구별합니다. 노트북 형태의 셀에서는 재생 버튼을 누르면 저장된 실제 실행 결과가 나타납니다. 브라우저가 Python을 실시간으로 실행하는 기능은 아닙니다. 공유 노트북에는 실행한 9개 코드 셀과 출력이 들어 있습니다.

## 자료와 새 연구의 연결

- [발표자료 안내와 다운로드](../experiments/seminar-guide.md)
- [45장 HTML 발표자료](../experiments/seminar/index.html)
- [PDF 발표자료](../experiments/seminar/seminar.pdf)
- [실행 결과가 포함된 노트북](../experiments/seminar/notebooks/manufacturing-shacl.ipynb)

발표자료 후반의 과거 실험은 당시의 탐색 결과입니다. 새 연구의 확증 결과로 읽지 않도록 [주장별 정리](2026-10-27-exploration-closeout.md)와 함께 봅니다. 새 연구는 [인증 상태와 제품 재검토 근거 비교](../experiments/evidence-report-study.md)로 범위를 좁혔습니다.

[새 오프라인 데모](../experiments/evidence-report-demo/index.html)는 작성한 네 가지 근거 상태, Python·OWL-RL 연결 점검과 SHACL 필드 검사, A/B/C 프롬프트를 보여 줍니다. 모델 답변은 미실행 상태입니다. 발표자료와 데모의 화면·다운로드·모바일 표시를 점검했지만 이 점검은 연구 효과를 측정한 실험이 아닙니다.
