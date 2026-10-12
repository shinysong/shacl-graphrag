# 실험 기록과 GitHub Pages 운영

실험 명세와 일지의 원본은 Markdown이다. GitHub에서 파일을 읽거나 MkDocs로 만든 사이트에서 탐색할 수 있다. GitHub Pages는 정적 파일을 게시하므로 실험 실행은 EC2에서 하고 공개할 기록을 저장소에 반영한다. [GitHub Pages 설명](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

## 실험 한 번을 기록하는 순서

1. [명세](../experiments/specification.md)의 조건과 기대값을 확인한다. 조건을 바꾸면 변경 이유를 일지에 적는다.
2. `uv run --locked python scripts/run_validation_experiment.py`를 실행한다. 재실행도 새 run으로 저장한다.
3. `docs/experiments/records/`의 결과와 `runs/`의 상세 보고서를 확인한다. 실패 결과도 보존한다.
4. [일지 양식](../journal/template.md)으로 관찰과 다음 결정을 적고 [일지 목록](../journal/index.md)에 링크한다.
5. 아래 명령으로 문서 빌드를 확인한다. 공개할 파일을 검토한 뒤 코드·입력·`uv.lock`·문서를 함께 commit한다.

이 실행기는 여섯 개의 합성 사례만 다루며 공개용 필드를 정해 저장한다. 실제 데이터나 API 응답을 도입할 때는 공개 필드를 다시 정한다. `.env`, 인증 정보, 페어링 링크와 원본 서비스 로그는 문서에 넣지 않는다. 로컬에서만 시험할 때는 실행기에 `--local-only`를 붙인다.

## 문서 빌드와 미리보기

```bash
uv sync --locked --group docs
uv run --locked --group docs mkdocs build --strict
uv run --locked --group docs mkdocs serve --dev-addr 127.0.0.1:8000
```

EC2에서 실행한 미리보기는 SSH 포트 전달로 접속한다. 생성한 `site/`는 Git에 넣지 않는다. MkDocs는 Markdown을 HTML로 변환하며 GitHub Pages에 배포할 수 있다. [MkDocs 배포 문서](https://www.mkdocs.org/user-guide/deploying-your-docs/)

## GitHub Pages 최초 공개

현재 저장소의 `cursor/add-readme-gitignore`에 반영한다는 기준으로 `.github/workflows/pages.yml`을 구성한다. PR에서는 문서 빌드를 검사하고 `cursor/add-readme-gitignore` push 또는 수동 실행에서는 사이트를 배포한다. 기본 브랜치가 다르면 workflow와 `mkdocs.yml`의 편집 링크를 함께 바꾼다.

저장소 관리자는 Settings → Pages → Build and deployment에서 Source를 GitHub Actions로 선택한다. 변경 파일과 `uv.lock`을 원격에 반영한 뒤 Actions의 Pages 작업이 성공했는지 확인한다. 기본 주소는 `https://shinysong.github.io/shacl-graphrag/`이며 실제 공개 여부는 배포 성공 후 확인한다. [GitHub의 사이트 생성 절차](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

실험 실행만으로 원격에 push하거나 사이트를 배포하지 않는다. GitHub Actions도 실험 결과 파일을 자동 commit하지 않는다. 공개 주기는 기록을 검토하고 저장소에 반영하는 주기에 따른다.

## 문서 작성

한국어 문서의 초안을 작성한 뒤 [im-not-ai의 humanize-korean 스킬](https://github.com/epoko77-ai/im-not-ai/tree/main/codex/skills/humanize-korean)로 윤문한다. 수치·명령·고유명사·주장의 강도를 유지하고 번역투와 반복 표현을 점검한다. 윤문 중간 파일은 `_workspace/`에 두고 사이트에서 제외한다.

문체 검사 결과는 실험의 사실 검증을 대신하지 않는다. 수치는 run 기록과 대조하고, 계획과 측정 결과를 구분해서 쓴다.
