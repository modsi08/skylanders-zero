#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade catalogue/UI only, preserving the installed USB startup code."""
import argparse
import datetime
import py_compile
import shutil
import subprocess
from pathlib import Path


def patch_app(text):
    # Remove the v0.4 integration if present. Restore the original small state API.
    import ast
    text=text.replace('from catalogue import catalogue, library_state\n','')
    if '    files, slots=library_state(DATA,portal)' in text:
        text=text.replace('    files, slots=library_state(DATA,portal)',
            "    files=[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(DATA.iterdir()) if p.is_file() and p.suffix.lower() in ('.bin','.dump','.dmp','.sky') and p.stat().st_size==1024]",1)
        text=text.replace('slots=slots','slots=portal.snapshot()',1)
    tree=ast.parse(text)
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name=='get_catalogue':
            lines=text.splitlines(keepends=True)
            start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
            del lines[start:node.end_lineno]
            text=''.join(lines)
            break
    if 'def state():' not in text or 'library_state(DATA,portal)' in text:
        raise ValueError('Unrecognised status API; no files were changed')
    if 'from identity_api import install_identity_routes' not in text:
        text='from identity_api import install_identity_routes\n'+text
    if 'install_identity_routes(app, DATA)' not in text:
        marker="if __name__=='__main__':"
        if marker not in text: raise ValueError('Unrecognised app startup; no files were changed')
        text=text.replace(marker,'install_identity_routes(app, DATA)\n\n'+marker,1)
    if 'from selection import install_selection_routes' not in text:
        text='from selection import install_selection_routes\n'+text
    if 'install_selection_routes(app, DATA, portal' not in text:
        marker="if __name__=='__main__':"
        check="lambda: globals().get('modes') is None or modes.snapshot()['mode']=='portal'"
        text=text.replace(marker,'install_selection_routes(app, DATA, portal, '+check+')\n\n'+marker,1)
    compile(text,'app.py','exec')
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,default=Path('/opt/skylanders-zero'))
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    target=args.target.resolve()
    if source==target:
        raise SystemExit('Extract the update into a separate directory first.')
    app=target/'app.py'
    patched=patch_app(app.read_text())
    for name in ('identity_api.py','selection.py','tools/upgrade_ui.py'):
        py_compile.compile(str(source/name),doraise=True)
    backup=target.parent/(target.name+'-before-catalogue-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    names=['app.py','templates/index.html','identity_api.py','selection.py','static/catalogue.js','catalog/figures.json']
    for name in names:
        path=target/name
        if path.exists():
            dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    active=subprocess.run(['systemctl','is-active','--quiet','skylanders-web'],check=False).returncode==0
    subprocess.run(['systemctl','stop','skylanders-web'],check=True)
    try:
        for name in names[1:]:
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,dest)
        app.write_text(patched)
    except Exception:
        for name in names:
            saved=backup/name
            if saved.exists():shutil.copy2(saved,target/name)
            elif (target/name).exists():(target/name).unlink()
        if active:subprocess.run(['systemctl','start','skylanders-web'],check=False)
        raise
    if active:subprocess.run(['systemctl','start','skylanders-web'],check=True)
    print('Catalogue and web UI updated. Existing USB startup and boot settings were preserved.')
    print('Backup:',backup)
    print('Refresh http://portal:8080 or use the Pi IP address. No reboot required.')

if __name__=='__main__':main()
