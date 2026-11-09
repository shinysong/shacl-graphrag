# Original welding measurement sufficiency

One purposively selected PP6 bead file from Tapia Suárez et al., Submerged Arc Welding Open Repository, DOI https://doi.org/10.5281/zenodo.15083865, CC BY 4.0. Original PP6 README bytes retained. Original HDF5 stays in the ignored local source cache; acquisition.json fixes its archive member, length, SHA256 and CRC. Complete 12.7GB archive was not downloaded or checksummed.

Run from repository root with the acquired original file:

```sh
uv run --locked --with h5py==3.16.0 python research/manufacturing-measurement-1/diagnostic-001/check.py
uv run --locked --with h5py==3.16.0 python research/manufacturing-measurement-1/diagnostic-001/diagnostic.py PATH_TO_PP6_01.hdf5 research/manufacturing-measurement-1/diagnostic-001/annotation.json NEW_OUTPUT.json
```

Six completed diagnostic slots are not six correct answers or six validated mappings. They inspect one consumed-development file after preliminary source inspection. Four slice conventions remain conditional and do not exhaust possible alignment transformations. None is selected. Do not describe their arithmetic as verified defect-interval current, calibrated physical truth, or an operating recommendation.

The file contains serialized configuration text among its attributes. This code never deserializes attributes. It rejects external/virtual datasets and object dtypes. Source hashes/CRC ensure local integrity only.

Internal run failures retain all six slots (see source-hash-failure.json). CLI annotation loading and output serialization failures occur outside that handler and must be preserved separately. source_sha256 denotes the expected digest on failures. Resources.txt measures this single local diagnostic process including uv, not graph-engine or retrieval performance.

The original Q8 and backend results remain frozen. Adding a measurement source is a separate source-access intervention, not a SHACL report treatment. Current-source association, index convention, coordinates, calibration and applicable document version remain unverified.
