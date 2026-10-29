# Seminar notebook interaction revision

User asks only: clarify slide15 inferencepurpose and remove code; slide22 focus on HOWLLM drafts RDF+SHACLShape, not heavygovernance; slides24/25 notebook-like cells with play revealing actual saved outputs, plus shared self-containedipynb. Keep slides30–45 exactly unchanged. Existing45slide presentation. No largerapp/research campaign.

Read only own request and authorized files, write only designatedoutput. No other reviews/secrets/heldoutgold/historicalrawQA.
- docs/experiments/seminar/slides.md, views/inference_purpose.html, views/kg_chat.html, theme.css, app.js
- scripts/build_seminar.py, scripts/build_seminar_notebook.py, scripts/seminar_manufacturing_examples.py
- docs/experiments/seminar/notebooks/manufacturing-shacl.ipynb (actual executed with NBClient, source/data embedded, no repo imports)
- docs/experiments/seminar/manufacturing/* (prior saved teachingoutputs)
- docs/experiments/seminar/index.html (parse notbase64dump), build-manifest.json, seminar.pdf, docs/experiments/seminar-guide.md
- scripts/prepare_chirpy.py, mkdocs.yml
- _workspace/seminar-notebook/before/slides.md and index.html (scopepreservationcomparison)
- https://github.com/RDFLib/pySHACL
- https://nbclient.readthedocs.io/en/latest/client.html
- https://nbformat.readthedocs.io/en/latest/format_description.html

Methods: inference explains supplied Bolt⊆Fastener⊆Component and inverse installedIn/hasPart result,not externaltruth. LLMscreen presenter-authored expectedRDF+SHACL from document AND separately supplied mandatorymanufacturerpolicy,not actualLLMresponse or learnedrule. No paidcalls. Notebook actualvalidationFalse, report focusP1/manufacturer/minCount, addedmanufacturertrue, inferredComponent/hasPart. Notebook repair is authoredteachinginput not evaluationgoldrepair. Oldbenchmark untouched. Heavygovernance intentionally moved into smalllabels/notes,not a missingexperiment.

Implementation: notebookvalidformat andselfcontained imports/constants, actuallyexecuted outputs; builder renders exactcode/stdout from selected cellIDs; ▶reveals storedoutputs instantly, neverclaims livePython; per-cell buttons accessible, reserveoutputspace, nooldflowcontrols. Staticguide/PDF showoutputs withoutclick; notebookdownload embeddedbytesmatch; rawHTMLassetsescaped. 30–45 source and generatedsections must remain identical. No runtimefreeformcodeexecution or API. Main handles finalactualbrowser/print/download checks after review.

Registered checks none, registry unrelated. Manual planned checks: notebookallcodecells executed with noerrors, source/outputbinding; desktop/mobile originalandrevealedbounds, eachbutton+download, PDF45withnotebookoutputs; MkDocsstrict+Chirpy, localHTTPguide lightdark, copiedipynbbyteequality. No paidcalls, oldresearchreruns,push/deploy/cloud/schedule. Keep errors/oldartifactbackup. Focus defects within user scope.
