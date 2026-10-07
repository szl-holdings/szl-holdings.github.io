#!/usr/bin/env python3
"""Bind the reviewed public SAMPLE replay and build a deterministic download."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path('estate/receipt-replay')
FILES = ('LICENSE', 'README.md', 'replay.py', 'requirements.lock', 'sample-input.json',
         'source-lock.json', 'measured-run.json')
SOURCE = '1467fcbd1ff57b955d588c73e64a541ebc16770f'
REPORT_FIELDS = {'schema', 'observed_at', 'evidence_class', 'scope', 'source', 'bundle_hashes',
                 'runtime', 'cases', 'conformance_checks', 'conformant', 'key_generation',
                 'effects_performed', 'external_services_called', 'production_authorization',
                 'production_runtime_status', 'independent_replay', 'hardware_measurement', 'energy_joules'}
CASE_FIELDS = {'id', 'fixture_evidence_class', 'verification_evidence_class', 'status',
               'reasons', 'signature_valid', 'key_trust', 'payload_sha256', 'envelope_sha256', 'checks'}
CHECK_FIELDS = {'expected_admission_status', 'required_reasons_present', 'expected_signature_validity'}


def closed(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Replay report contains missing or unknown fields')


def hex_digest(value):
    if not isinstance(value, str) or re.fullmatch(r'[a-f0-9]{64}', value) is None:
        raise ValueError('Replay digest is malformed')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_object(raw):
    def unique(pairs):
        value = {}
        for name, item in pairs:
            if name in value:
                raise ValueError('Duplicate replay JSON member')
            value[name] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('Replay JSON must be an object')
    return value


def generate(root=ROOT):
    folder = root / RELATIVE
    raw = {name: (folder / name).read_bytes() for name in FILES}
    if any(b'\r' in b or len(b) > 200000 or b'-----BEGIN PRIVATE KEY-----' in b for b in raw.values()):
        raise ValueError('Replay inputs require bounded LF bytes without private keys')
    report = read_object(raw['measured-run.json'])
    lock = read_object(raw['source-lock.json'])
    fixture = read_object(raw['sample-input.json'])
    if digest(raw['source-lock.json']) != 'e590d54e19acb59d10268256a9755b557d76edc1719ca9f3f726a1733461146b':
        raise ValueError('Canonical source lock differs from reviewed bytes')
    closed(report, REPORT_FIELDS)
    closed(report['source'], {'repository', 'commit', 'files', 'byte_binding'})
    closed(report['bundle_hashes'], {'replay.py', 'source-lock.json', 'sample-input.json', 'requirements.lock'})
    closed(report['runtime'], {'implementation', 'python', 'operating_system', 'dependencies', 'installed_dependency_byte_integrity'})
    closed(report['key_generation'], {'performed', 'in_memory', 'persisted_private_key_material', 'trust'})
    closed(report['conformance_checks'], {'passed', 'total'})
    key = report['key_generation']
    runtime = report['runtime']
    if (key['performed'] is not True or key['in_memory'] is not True
            or key['persisted_private_key_material'] is not False or key['trust'] != 'SAMPLE_LOCAL'
            or runtime['dependencies'] != lock['dependencies'] or runtime['implementation'] != 'CPython'
            or runtime['installed_dependency_byte_integrity'] != 'UNKNOWN'
            or not re.fullmatch(r'3\.(11|12)\.[0-9]+', runtime['python'])
            or runtime['operating_system'] not in {'Windows', 'Linux', 'Darwin'}
            or report['scope'] != 'local verifier conformance over SAMPLE fixtures'
            or report['effects_performed'] != [] or report['hardware_measurement'] != 'UNAVAILABLE'
            or report['energy_joules'] != 'UNAVAILABLE'
            or report['source']['repository'] != lock['repository']
            or report['source']['byte_binding'] != 'MEASURED'
            or type(report['conformance_checks']['passed']) is not int
            or type(report['conformance_checks']['total']) is not int
            or not isinstance(report['observed_at'], str)
            or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z', report['observed_at'])):
        raise ValueError('Replay runtime, keys or scope were promoted')
    if (report.get('schema') != 'szl.receipt-replay-result/v1'
            or report.get('evidence_class') != 'MEASURED'
            or report.get('source', {}).get('commit') != SOURCE
            or lock.get('commit') != SOURCE or report['source']['files'] != lock['files']
            or fixture.get('evidence_class') != 'SAMPLE'
            or report.get('conformant') is not True
            or report.get('conformance_checks') != {'passed': 12, 'total': 12}
            or report.get('production_authorization') != 'BLOCKED'
            or report.get('production_runtime_status') != 'UNKNOWN'
            or report.get('independent_replay') != 'NOT RUN'
            or report.get('external_services_called') != []):
        raise ValueError('Replay scope, source or recorded outcome is invalid')
    for name in ('replay.py', 'source-lock.json', 'sample-input.json', 'requirements.lock'):
        hex_digest(report['bundle_hashes'][name])
        if report.get('bundle_hashes', {}).get(name) != digest(raw[name]):
            raise ValueError('Recorded replay does not bind current bundle bytes: ' + name)
    expected = [('complete_signed', 'PASS', True, []),
                ('tampered_payload', 'INCOMPLETE', False, ['signature-mismatch']),
                ('incomplete_signed', 'INCOMPLETE', True, ['missing-subject:runtime_witness', 'evidence-missing:runtime_witness', 'evidence-role-set-mismatch']),
                ('unsigned_honest', 'INCOMPLETE', False, ['dsse-signature-count-not-one', 'signature-not-present'])]
    cases = report.get('cases', [])
    if len(cases) != len(expected):
        raise ValueError('Four replay cases are required')
    for case, (name, status, signature, reasons) in zip(cases, expected):
        closed(case, CASE_FIELDS)
        closed(case['checks'], CHECK_FIELDS)
        hex_digest(case['payload_sha256'])
        hex_digest(case['envelope_sha256'])
        if (case.get('id') != name or case.get('status') != status
                or case.get('signature_valid') is not signature
                or case.get('fixture_evidence_class') != 'SAMPLE'
                or case.get('verification_evidence_class') != 'MEASURED'
                or case.get('key_trust') != 'SAMPLE_LOCAL'
                or case['reasons'] != sorted(reasons)
                or any(value is not True for value in case['checks'].values())):
            raise ValueError('Replay case was omitted or promoted')
    manifest = {'schema': 'szl.receipt-replay-bundle/v1', 'evidence_class': 'DECLARED',
                'source_revision': SOURCE, 'authority': 'Repository-declared integrity; independent identity UNKNOWN',
                'files': {name: {'sha256': digest(b), 'bytes': len(b)} for name, b in raw.items()}}
    encoded = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zipped:
        for name, b in sorted({**raw, 'bundle-manifest.json': encoded}.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 7, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, b)
    return encoded, archive.getvalue()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    try:
        manifest, archive = generate()
        outputs = {'bundle-manifest.json': manifest, 'receipt-replay.zip': archive}
        for name, raw in outputs.items():
            path = ROOT / RELATIVE / name
            if args.check:
                if path.read_bytes() != raw:
                    raise ValueError('Published replay output differs: ' + name)
            else:
                path.write_bytes(raw)
        print(json.dumps({'bundle_sha256': digest(archive), 'files': len(FILES) + 1, 'check': args.check}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('Replay bundle error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
