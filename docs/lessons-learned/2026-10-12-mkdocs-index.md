# 2026-10-12 MkDocs의 문서 첫 페이지 충돌

## Context

기존 `docs/README.md`를 유지하면서 사이트 첫 페이지로 `docs/index.md`를 추가했다.

## What happened

MkDocs가 같은 경로에 두 첫 페이지를 발견해 경고를 냈고 `mkdocs build --strict`가 실패했다.

## Lesson

사이트의 첫 페이지는 `index.md`로 정하고 `mkdocs.yml`의 `exclude_docs`에서 루트 `/README.md`를 제외한다. GitHub용 문서 목록은 유지할 수 있다.

## Follow-up

- [x] 사이트 첫 페이지를 하나로 지정하고 strict 빌드를 다시 실행한다.
