# SPDX-License-Identifier: GPL-3.0-or-later
"""Sixteen saved choices, separate from figures currently announced over USB."""
import json
import os
import threading
import time
from pathlib import Path
from flask import jsonify, request


class Selection:
    def __init__(self, folder, portal, path=None, timeout=3.0):
        self.folder = Path(folder)
        self.portal = portal
        self.path = Path(path) if path else self.folder.parent/'selection.json'
        self.timeout = timeout
        self.lock = threading.RLock()
        self.actions = threading.Lock()
        self.files = [None]*16
        self.error = None
        try:
            saved = json.loads(self.path.read_text())
            files = saved['files']
            if (not isinstance(files, list) or len(files) != 16 or any(f is not None and not self.valid_name(f) for f in files)
                    or len([f for f in files if f is not None]) != len(set(f for f in files if f is not None))):
                raise ValueError('Invalid selection')
            self.files = files
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError):
            self.error = 'Cannot read saved selection.json; restore or rename it before changing the selection.'

    @staticmethod
    def valid_name(name):
        return (isinstance(name, str) and bool(name) and name == os.path.basename(name)
                and Path(name).suffix.lower() in ('.bin', '.dump', '.dmp', '.sky'))

    def validate_file(self, name):
        if not self.valid_name(name): raise ValueError('Invalid figure filename')
        path = self.folder/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != 1024:
            raise ValueError('Figure file is missing or is not a 1024-byte dump')

    def slot_index(self, slot):
        if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= 16:
            raise ValueError('Select a slot from 1 to 16')
        return slot-1

    def snapshot(self):
        with self.lock:
            return dict(slots=[dict(slot=i+1, file=f) for i, f in enumerate(self.files)],
                        selection_error=self.error)

    def persist(self, files):
        if self.error: raise ValueError(self.error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        with temp.open('w') as out:
            json.dump(dict(files=files), out);out.flush();os.fsync(out.fileno())
        os.replace(temp, self.path)
        fd = os.open(self.path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        self.files = files

    def add(self, name):
        self.validate_file(name)
        with self.actions, self.lock:
            if name in self.files: return self.files.index(name)+1
            try: index = self.files.index(None)
            except ValueError: raise ValueError('All 16 selection slots are full; remove a choice first')
            files = list(self.files);files[index] = name;self.persist(files)
            return index+1

    def deactivate_locked(self):
        # Let the existing protocol announce the removal and complete its five
        # reports. Never load a new figure while the old one is still announced.
        for slot in self.portal.snapshot():
            if slot['file'] is not None and slot['state'] != 2:
                self.portal.unload(slot['slot']-1)
        self.portal.send_status()
        deadline = time.monotonic()+self.timeout
        while any(slot['file'] is not None for slot in self.portal.snapshot()):
            if time.monotonic() >= deadline:
                raise TimeoutError('Previous figure is still being removed. No new figure was activated; wait and try again.')
            time.sleep(.02)

    def activate(self, slot):
        index = self.slot_index(slot)
        with self.actions:
            with self.lock: name = self.files[index]
            if name is None: raise ValueError('This selection slot is empty')
            self.validate_file(name)  # Reject bad choices before removing the current figure.
            present = [s for s in self.portal.snapshot() if s['file'] is not None]
            if len(present) == 1 and present[0]['file'] == name and present[0]['state'] in (1, 3):
                return
            self.deactivate_locked()
            self.portal.load(name, index)
            self.portal.send_status()

    def deactivate(self):
        with self.actions: self.deactivate_locked()

    def remove(self, slot):
        index = self.slot_index(slot)
        with self.actions:
            with self.lock: name = self.files[index]
            if name is not None and any(s['file'] == name for s in self.portal.snapshot()):
                self.deactivate_locked()
            with self.lock:
                files = list(self.files);files[index] = None;self.persist(files)


def install_selection_routes(app, folder, portal, portal_mode=None):
    selection = Selection(folder, portal)
    app.extensions['figure_selection'] = selection

    @app.get('/api/selection')
    def selection_state(): return jsonify(**selection.snapshot())

    @app.post('/api/selection/<operation>')
    def selection_change(operation):
        value = request.get_json(silent=True)
        value = value if isinstance(value, dict) else {}
        try:
            if operation == 'add':
                slot = selection.add(value.get('name'))
                return jsonify(ok=True, slot=slot, **selection.snapshot())
            if operation == 'activate':
                if portal_mode is not None and not portal_mode():
                    return jsonify(error='Select Portal mode first'), 409
                selection.activate(value.get('slot'))
            elif operation == 'deactivate': selection.deactivate()
            elif operation == 'remove': selection.remove(value.get('slot'))
            else: return jsonify(error='Unknown selection action'), 404
        except ValueError as exc: return jsonify(error=str(exc)), 400
        except TimeoutError as exc: return jsonify(error=str(exc)), 409
        except OSError as exc: return jsonify(error=str(exc)), 503
        return jsonify(ok=True, **selection.snapshot())
