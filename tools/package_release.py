#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a source ZIP from an explicit allowlist; no dumps or runtime data."""
import argparse
import stat
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES={'.gitignore','.gitattributes','README.md','COPYING','THIRD_PARTY.md','VALIDATION.md',
       'CHANGELOG.md','VERSION','config.env.example','requirements.txt','install.sh',
       'upgrade-ui.sh','setup-gadget.sh','diagnose.sh','app.py','audio.py','portal.py',
       'transport.py','modes.py','identity_api.py','selection.py','catalogue.py'}
DIRECTORIES={'catalog','static','templates','usb','tools','tests','systemd','docs','LICENSES','vendor','.github','figures'}
BANNED={'.bin','.dump','.dmp','.sky','.pyc','.pyo','.ko','.o','.xz','.zst','.log','.zip','.gz'}


def source_files(root=ROOT):
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root)
        if len(rel.parts)==1 and rel.name not in FILES:continue
        if len(rel.parts)>1 and rel.parts[0] not in DIRECTORIES:continue
        if any(part in ('__pycache__','.venv','.git','dist','build','.tmp_versions') for part in rel.parts):continue
        if rel.parts[0]=='figures' and rel.as_posix()!='figures/.gitkeep':continue
        if path.name=='.env' or path.name.startswith('.env.'):continue
        if path.suffix.lower() in BANNED or '.original' in path.name:continue
        if path.name in ('raw-bridge','selection.json','device-mode.json','selection.tmp','device-mode.tmp','Module.symvers','modules.order'):continue
        yield path


def package(output, root=ROOT):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            rel=Path('skylanders-zero')/path.relative_to(root)
            info=zipfile.ZipInfo.from_file(path,arcname=rel.as_posix())
            info.compress_type=zipfile.ZIP_DEFLATED
            # GitHub clones preserve git's executable bit; ZIP extraction preserves
            # this Unix mode too. Also document bash install.sh for other extractors.
            if path.suffix=='.sh':info.external_attr=(stat.S_IFREG|0o755)<<16
            archive.writestr(info,path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any(Path(name).suffix.lower() in BANNED for name in archive.namelist())
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output=args.output or ROOT/'dist'/f"skylanders-zero-{(ROOT/'VERSION').read_text().strip()}-source.zip"
    print(package(output))
