# SPDX-License-Identifier: GPL-3.0-or-later
"""Small on-demand header API; no catalogue parsing or portal lock in this process."""
import os
import stat
from pathlib import Path
from flask import jsonify, request, send_file

ROOT = Path(__file__).resolve().parent


def read_identities(folder, names):
    if not isinstance(names, list) or len(names) > 16 or any(
        not isinstance(name, str) or not name or name != os.path.basename(name)
        or name in (".", "..") or Path(name).suffix.lower() not in (".bin", ".dump", ".dmp", ".sky")
        for name in names
    ):
        raise ValueError("Provide up to 16 figure filenames")
    result = {}
    for name in names:
        fd = None
        try:
            fd = os.open(Path(folder)/name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size != 1024:
                raise ValueError("Not a 1024-byte figure file")
            header = os.read(fd, 32)
            if len(header) != 32:
                raise ValueError("Incomplete figure header")
            result[name] = dict(character_id=int.from_bytes(header[16:19], "little"),
                                variant_id=int.from_bytes(header[28:30], "little"),
                                blank=header in (bytes(32), bytes([255])*32))
        except (OSError, ValueError):
            result[name] = dict(error="Cannot read figure header")
        finally:
            if fd is not None: os.close(fd)
    return result


def install_identity_routes(app, folder):
    @app.get('/api/catalogue')
    def catalogue_document():
        # Stream the stored file. Do not decode/encode 718 metadata records on the Pi.
        return send_file(ROOT/'catalog/figures.json', conditional=True)

    @app.get('/catalogue.js')
    def catalogue_javascript():
        return send_file(ROOT/'static/catalogue.js', conditional=True)

    @app.post('/api/identities')
    def figure_identities():
        value = request.get_json(silent=True)
        try:
            result = read_identities(folder, value.get('names') if isinstance(value, dict) else None)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(identities=result)
