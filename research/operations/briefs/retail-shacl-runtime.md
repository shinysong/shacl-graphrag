# Existing pySHACL dependencies in bounded container

Review modified retail_python_runner.py, new retail_shacl_runtime.py and
research/retail-evaluation/executable-input-interface-v1.json.
One offline improvement: copy already installed pyshacl and active transitive
distribution files from current venv site-packages into isolated staged directory.
No downloads, install, image build, service or model calls. Console entrypoints
outside purelib skipped; no workspace/source/ref/secret mounts. Record versions
and exact file hashes. Runner boolean option mounts only fixed staged directory
readonly at/deps, verifies exact file set/hashes, PYTHONPATH=/deps. Existing
nonroot/networknone/readonly and output/time/resource limits unchanged.

After independent reviews run
`UV_OFFLINE=true uv run --locked --group workbench python -m scripts.retail_shacl_runtime`.
Fixed authored Python artifact imports pyshacl/rdflib and validates two tiny
authored graphs against minInclusive0: positive pass, negative fail. Save actual
Turtle validation reports, versions, execution failures, cleanup. Stop on any
failure; do not install or automatically retry. No generated shapes yet.
No grammar/supported-subset/security completeness claim from this smoke.
Explicit input-interface document fixes future communication only, no prior
Python artifact/result modifications and no claim construction exposure is matched.
Reviewers static only, no tests/API/secrets/heldout/modelanswers/otherreviews/edits.
