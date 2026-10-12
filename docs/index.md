# SHACL GraphRAG Lab

온톨로지 제약을 검색과 답변 생성 사이에 넣으면 잘못된 근거를 줄일 수 있을까? 이곳에 실험 조건과 실행 결과, 진행 중에 바뀐 판단을 기록한다.

현재는 합성 RDF로 SHACL 검증과 채점을 확인하는 E0 단계다. YAGO와 LLM을 사용한 비교 실험은 아직 진행하지 않았다.

## 실험 따라가기

| 읽을 거리 | 내용 |
| --- | --- |
| [실험 명세](experiments/specification.md) | 연구 질문, 비교 조건, 채점 기준, 진행 순서 |
| [실행 기록](experiments/records/index.md) | 실행마다 생성한 결과와 환경 정보 |
| [연구 일지](journal/index.md) | 시도한 이유, 관찰, 해석, 다음 결정 |
| [기록 운영 방법](setup/recording.md) | 재실행과 문서 미리보기, GitHub Pages 공개 절차 |
| [환경 구성](setup/bootstrap.md) | Ubuntu와 uv로 실험 환경 준비 |
| [시행착오](lessons-learned/README.md) | 반복하지 않으려는 실수와 해결 방법 |

## 기록이 쌓이는 흐름

명세를 정하고 실험을 실행하면 결과 요약과 JSON 기록이 생긴다. 그 결과를 읽고 연구 일지에 판단을 남긴다. 문서를 commit하고 push하면 GitHub Actions가 사이트를 다시 만든다. 실행 중인 EC2 화면을 실시간으로 보여주는 방식은 아니다.

여러 프로젝트를 모으는 lab이 생기면 이 사이트를 프로젝트별 기록으로 연결한다. 공통 실험 도구와 글은 별도 lab에 두고 이 프로젝트의 재현 자료는 코드와 함께 유지할 계획이다.
