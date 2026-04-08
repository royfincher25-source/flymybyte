#!/usr/bin/env python3
"""
Generate MANIFEST.json for incremental web UI updates.

Scans all files listed in FILES_TO_UPDATE from constants.py,
computes MD5 hashes, and writes MANIFEST.json to the project root.

This manifest is used by the router's update mechanism to determine
which files need to be downloaded (only changed/new/removed files).

Usage:
    python3 scripts/generate_manifest.py
"""

import hashlib
import json
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src', 'web_ui'))

from core.constants import FILES_TO_UPDATE


def compute_md5(filepath: str) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (FileNotFoundError, PermissionError) as e:
        print(f"WARNING: Cannot read {filepath}: {e}", file=sys.stderr)
        return None


def generate_manifest() -> dict:
    """Generate manifest dict from FILES_TO_UPDATE."""
    manifest = {
        'version': '1.0',
        'files': {},
        'stats': {'total': 0, 'ok': 0, 'missing': 0},
    }

    for source_path, dest_path in FILES_TO_UPDATE.items():
        # FILES_TO_UPDATE paths are relative to src/ (e.g. 'web_ui/app.py')
        # Special case: VERSION is in project root
        if source_path == 'VERSION':
            full_source = os.path.join(PROJECT_ROOT, source_path)
        else:
            full_source = os.path.join(PROJECT_ROOT, 'src', source_path)
        md5 = compute_md5(full_source)

        if md5:
            manifest['files'][source_path] = {
                'dest': dest_path,
                'md5': md5,
                'size': os.path.getsize(full_source),
            }
            manifest['stats']['ok'] += 1
        else:
            manifest['stats']['missing'] += 1
            print(f"WARNING: Missing file: {full_source}", file=sys.stderr)

        manifest['stats']['total'] += 1

    return manifest


def main():
    print(f"Scanning project: {PROJECT_ROOT}")
    manifest = generate_manifest()

    output_path = os.path.join(PROJECT_ROOT, 'MANIFEST.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    stats = manifest['stats']
    print(f"MANIFEST.json generated: {stats['ok']}/{stats['total']} files ({stats['missing']} missing)")
    print(f"Output: {output_path}")
    return 0 if stats['missing'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
