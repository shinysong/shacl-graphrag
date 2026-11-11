# Chirpy site

Chirpy 7.6.0 (MIT) supplies the layouts, search, categories, archives, dark mode and responsive navigation. `LICENSE` retains the upstream starter attribution; the copied home layout and Sass entry point come from the same theme release.

Canonical content stays in `docs/`. `scripts/prepare_chirpy.py` copies only public Markdown/JSON plus this template to ignored `_workspace/chirpy-source/`, adds Jekyll metadata and rewrites links while retaining existing URLs. Fenced Mermaid diagrams automatically enable the theme’s Mermaid renderer on their page. Keep diagram labels short enough for mobile screens. Do not edit generated pages.

The primary sidebar is Home, About, and Archives. Home presents the research
overview and recent posts; Archives lists dated posts and links to the execution-record index.
Protocol, Runs, Journal, Setup, Categories, and Tags retain their existing URLs
but are reached through content links,
search, or bookmarks. Edit `TABS` and pinned post names in `scripts/prepare_chirpy.py`
to change the navigation; editing generated `_tabs` or `site/` has no effect on the next build.

Use Ruby 3.4:

```bash
BUNDLE_GEMFILE=website/Gemfile bundle install
./scripts/build_site.sh
```

The final artifact is `site/`. Python remains managed by uv. The legacy MkDocs build checks source documents only; CI always runs Chirpy last before uploading the artifact. The theme uses its default public CDN assets. No comments, analytics or offline cache are enabled.

Daily article publication is deliberately opt-in. Put the finished dated journal
Markdown path and any new `docs/assets/images/` PNG/SVG paths in ignored
`_workspace/publication/ready.json`, for example
`{"paths":["docs/journal/2026-11-11-example.md"]}`. The installed user timer
runs at 09:00 Asia/Seoul. It copies only those paths into a clean checkout of the
Pages branch, runs strict MkDocs and Chirpy checks, and pushes only if they pass.
Failed attempts stay queued and receive an ignored JSON receipt under
`_workspace/publication/attempts/`. No queue means no push. The timer does not
write articles or publish unrelated dirty workspace files. It needs this EC2
host and GitHub SSH access; `systemctl --user list-timers` shows the next run.
