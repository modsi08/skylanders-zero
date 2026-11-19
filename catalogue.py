# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline figure identification. Never changes a dump or its save data."""
import copy
import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Catalogue:
    def __init__(self, path=ROOT / 'catalog/figures.json'):
        document = json.loads(Path(path).read_text())
        self.records = {}
        self.characters = {}
        self.character_types = {}
        for row in document['figures']:
            key = (row['character_id'], row['variant_id'])
            if key in self.records:
                raise ValueError(f'Duplicate catalogue identity: {key}')
            self.records[key] = row
            self.characters.setdefault(key[0], row)
            self.character_types.setdefault(key[0], set()).add(row['figure_type'])
        self.sources = document['sources']
        self.cache = {}
        self.lock = threading.Lock()

    def identify(self, data):
        if len(data) < 32:
            raise ValueError('Figure header must contain at least 32 bytes')
        character_id = int.from_bytes(data[0x10:0x13], 'little')
        variant_id = int.from_bytes(data[0x1c:0x1e], 'little')
        blank = data[:32] == bytes(32) or data[:32] == bytes([255]) * 32
        row = None if blank else self.records.get((character_id, variant_id))
        if row:
            return dict(copy.deepcopy(row), match='exact', known_character=True,
                        known_variant=True)
        base = None if blank else self.characters.get(character_id)
        return dict(character_id=character_id, variant_id=variant_id,
                    name=base['character_name'] if base else 'Unknown figure',
                    character_name=base['character_name'] if base else None,
                    variant_name='Unknown variant',
                    element=base['element'] if base else None,
                    figure_type=base['figure_type'] if base and len(self.character_types[character_id]) == 1 else 'Unknown',
                    edition_game=None, abilities=[], ps3_supported=None,
                    match='character_only' if base else 'unknown',
                    known_character=bool(base), known_variant=False,
                    notes=['Blank or erased header; cannot identify this figure.'] if blank else
                          ['Character known; this variant is not in the catalogue.'] if base else
                          ['This character ID is not in the catalogue.'])

    def identify_file(self, path):
        """Cache small headers by filesystem identity; game writes invalidate the entry."""
        path = Path(path)
        with self.lock:
            stat = path.stat()
            key = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            cached = self.cache.get(path)
            if cached and cached[0] == key:
                return copy.deepcopy(cached[1])
            with path.open('rb') as source:
                result = self.identify(source.read(32))
            if len(self.cache) >= 2048:
                self.cache.clear()
            self.cache[path] = (key, result)
            return copy.deepcopy(result)


catalogue = Catalogue()


def library_state(folder, portal):
    """Shared by this release and the UI-only upgrade for existing installations."""
    files = []
    # Disk scans and metadata lookups must never hold the USB protocol lock.
    # Slow SD cards / large libraries otherwise delay Q/W/S replies to the game.
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() not in ('.bin', '.dump', '.dmp', '.sky'):
            continue
        try:
            if not path.is_file() or path.stat().st_size != 1024:
                continue
            info = catalogue.identify_file(path)
            files.append(dict(name=path.name, bytes=1024, figure=info))
        except (FileNotFoundError, PermissionError, ValueError):
            # A disappearing/bad file must not take down the status endpoint.
            continue
    with portal.lock:
        slots = portal.snapshot()
        headers = [bytes(active['data'][:32]) if active else None for active in portal.slots]
    # Only the tiny consistent slot/header snapshot above needs the portal lock.
    for slot, header in zip(slots, headers):
        slot['figure'] = catalogue.identify(header) if header is not None else None
    return files, slots
