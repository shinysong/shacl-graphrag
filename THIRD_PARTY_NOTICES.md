# License scope and third-party notices

The owner selected Apache-2.0 for original project code on 2026-11-16. See LICENSE and NOTICE. Existing authorship and third-party notices remain applicable. Authored synthetic Factory Lab fixtures are distributed with the project under Apache-2.0; they contain fictional entities, not factory measurements.

## Bundled browser dependency

Cytoscape.js 3.34.3 is vendored at `apps/factory_lab/static/vendor/cytoscape-3.34.3.min.js`; retain its MIT license at `apps/factory_lab/static/vendor/cytoscape-LICENSE.txt`. No CDN is needed by the public demo.

## Installed Python dependencies

Dependencies installed from `uv.lock` are separate works under their own distribution licenses. The release inventory records installed distribution names, versions, license metadata and available license-file hashes; it is not a blanket relicensing statement. The public demo uses HTTPX, RDFLib and pySHACL and their transitive dependencies. The research repository also installs packages not needed by the demo.

## Research and website materials

YAGO retains CC BY 4.0 attribution in `experiments/yago/NOTICE.md`. Other source-grounded materials retain `research/source-grounded-1/DATA_LICENSES.txt` and adjacent acquisition/license records. Website theme terms remain in `website/LICENSE`. Paper illustrations and excerpts retain their source attribution and are not covered by the root license. These datasets and website assets are not required to run the public Factory Lab demo.

Saved demo answers are historical generated outputs, retained for inspection with source hashes and model metadata. They are not expert-approved industrial instructions or a guarantee of model availability. The root code license does not override third-party service terms.

## Local answer Markdown rendering

- Marked 18.2.1, MIT, https://github.com/markedjs/marked.
- DOMPurify 3.4.18, Apache-2.0 OR MPL-2.0 (used under Apache-2.0), https://github.com/cure53/DOMPurify.
- Distributed browser files, original licenses, pinned source URLs and SHA-256 hashes are in `apps/factory_lab/public_static/vendor/`. No CDN request is needed at runtime.
