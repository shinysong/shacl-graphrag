# Chirpy site

Chirpy 7.6.0 (MIT) supplies the layouts, search, categories, archives, dark mode and responsive navigation. `LICENSE` retains the upstream starter attribution; the copied home layout and Sass entry point come from the same theme release.

Canonical content stays in `docs/`. `scripts/prepare_chirpy.py` copies only public Markdown/JSON plus this template to ignored `_workspace/chirpy-source/`, adds Jekyll metadata and rewrites links while retaining existing URLs. Fenced Mermaid diagrams automatically enable the theme’s Mermaid renderer on their page. Keep diagram labels short enough for mobile screens. Do not edit generated pages.

Use Ruby 3.4:

```bash
BUNDLE_GEMFILE=website/Gemfile bundle install
./scripts/build_site.sh
```

The final artifact is `site/`. Python remains managed by uv. The legacy MkDocs build checks source documents only; CI always runs Chirpy last before uploading the artifact. The theme uses its default public CDN assets. No comments, analytics or offline cache are enabled.
