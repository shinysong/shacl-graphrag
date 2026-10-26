import copy
import hashlib
import json
import os

import pytest

from scripts import industrial_source_snapshot as snapshot


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    # Small authored fixture bytes, not copied upstream schemas or downloaded data.
    directory = tmp_path / 'sources'; directory.mkdir()
    records = []
    for filename in ['item.json', 'purchase_order_item.json', 'purchase_receipt_item.json',
                     'quality_inspection.json', 'license.txt']:
        payload = ('fixture:' + filename).encode()
        (directory / filename).write_bytes(payload)
        records.append({'path': 'upstream/'+filename, 'saved_as': filename,
                        'url': 'https://example.invalid/pinned/'+filename,
                        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
    manifest = {'source': 'fixture', 'branch': 'test', 'commit': 'a'*40, 'records': records}
    pin = tmp_path / 'pin.json'; pin.write_text(json.dumps(manifest))
    monkeypatch.setattr(snapshot, 'PIN_PATH', pin)
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    return directory, copy.deepcopy(manifest)


def save(directory, manifest):
    (directory / 'manifest.json').write_text(json.dumps(manifest))


def test_complete_bundle_returns_verified_bytes_without_mutation(bundle):
    directory, manifest = bundle
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    loaded, payloads = snapshot.validate_snapshot(directory)
    assert loaded == manifest
    assert payloads['license.txt'] == b'fixture:license.txt'
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


@pytest.mark.parametrize('index', [0, 1, 2, 3, 4])
def test_missing_required_record_rejected_even_when_file_exists(bundle, index):
    directory, manifest = bundle
    manifest['records'].pop(index); save(directory, manifest)
    with pytest.raises(ValueError, match='exactly'):
        snapshot.validate_snapshot(directory)


def test_duplicate_cannot_replace_required_record(bundle):
    directory, manifest = bundle
    manifest['records'][-1] = manifest['records'][0]; save(directory, manifest)
    with pytest.raises(ValueError, match='duplicate'):
        snapshot.validate_snapshot(directory)


@pytest.mark.parametrize('field', ['source', 'branch', 'commit'])
def test_changed_pin_rejected(bundle, field):
    directory, manifest = bundle
    manifest[field] = 'changed'; save(directory, manifest)
    with pytest.raises(ValueError, match='pin mismatch'):
        snapshot.validate_snapshot(directory)


@pytest.mark.parametrize('field,value', [('saved_as', '../outside.json'), ('url', 'https://example.invalid/other'),
                                        ('bytes', 999), ('sha256', '0'*64)])
def test_manifest_cannot_redeclare_file_identity(bundle, field, value):
    directory, manifest = bundle
    manifest['records'][0][field] = value; save(directory, manifest)
    with pytest.raises(ValueError, match='record does not match'):
        snapshot.validate_snapshot(directory)


def test_rehashed_modified_file_is_not_trusted(bundle):
    directory, manifest = bundle
    altered = b'other content'
    (directory/'item.json').write_bytes(altered)
    manifest['records'][0].update(bytes=len(altered), sha256=hashlib.sha256(altered).hexdigest())
    save(directory, manifest)
    with pytest.raises(ValueError, match='record does not match'):
        snapshot.validate_snapshot(directory)


def test_changed_bytes_rejected(bundle):
    directory, _ = bundle
    (directory/'item.json').write_bytes(b'wrong')
    with pytest.raises(ValueError, match='bytes differ'):
        snapshot.validate_snapshot(directory)


def test_missing_or_symlinked_license_rejected(bundle, tmp_path):
    directory, _ = bundle
    license_path = directory/'license.txt'; license_path.unlink()
    with pytest.raises(ValueError, match='regular file'):
        snapshot.validate_snapshot(directory)
    other = tmp_path/'outside-license'; other.write_bytes(b'fixture:license.txt')
    license_path.symlink_to(other)
    with pytest.raises(ValueError, match='regular file'):
        snapshot.validate_snapshot(directory)


def test_input_record_order_does_not_change_snapshot(bundle):
    directory, manifest = bundle
    manifest['records'].reverse(); save(directory, manifest)
    assert len(snapshot.validate_snapshot(directory)[1]) == 5


@pytest.mark.parametrize('kind', ['directory', 'fifo', 'symlink'])
def test_manifest_special_files_rejected_without_blocking(bundle, kind, tmp_path):
    directory, _ = bundle
    path = directory/'manifest.json'; payload = path.read_bytes(); path.unlink()
    if kind == 'directory':
        path.mkdir()
    elif kind == 'fifo':
        os.mkfifo(path)
    else:
        other = tmp_path/'other.json'; other.write_bytes(payload); path.symlink_to(other)
    with pytest.raises(ValueError, match='regular file'):
        snapshot.validate_snapshot(directory)


def test_manifest_read_is_bounded(bundle):
    directory, _ = bundle
    (directory/'manifest.json').write_bytes(b' ' * 1_000_001)
    with pytest.raises(ValueError, match='byte limit'):
        snapshot.validate_snapshot(directory)


def test_source_fifo_rejected_without_blocking(bundle):
    directory, _ = bundle
    path = directory/'license.txt'; path.unlink(); os.mkfifo(path)
    with pytest.raises(ValueError, match='regular file'):
        snapshot.validate_snapshot(directory)
