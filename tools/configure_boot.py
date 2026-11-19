#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backed-up, idempotent configuration changes for Raspberry Pi OS."""
import argparse
import re
import shutil
from pathlib import Path

START='# BEGIN skylanders-zero'
END='# END skylanders-zero'


def overlay_config(text):
    lines=text.splitlines();result=[];managed=False;section='all'
    for line in lines:
        if line==START:managed=True;continue
        if line==END:managed=False;continue
        if managed:continue
        match=re.fullmatch(r'\s*\[([^]]+)\]\s*',line)
        if match:section=match.group(1)
        # Replace only unconditional generic/device-role entries. Keep other models' settings.
        if section=='all' and re.fullmatch(r'\s*dtoverlay=dwc2(?:,dr_mode=(?:peripheral|host|otg))?\s*',line):continue
        result.append(line)
    return '\n'.join(result).rstrip()+'\n\n'+START+'\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n'+END+'\n'


def unblock_cmdline(text):
    tokens=text.split();result=[]
    for token in tokens:
        if token.startswith('module_blacklist='):
            kept=[name for name in token.split('=',1)[1].split(',') if name not in ('dwc2','raw_gadget')]
            if kept:result.append('module_blacklist='+','.join(kept))
        else:result.append(token)
    return ' '.join(result)+'\n'


def validate(boot,etc):
    boot,etc=Path(boot),Path(etc)
    manual=etc/'modprobe.d/usb-manual-test.conf'
    if manual.exists():
        allowed={'blacklist dwc2','blacklist raw_gadget','install dwc2 /bin/false','install raw_gadget /bin/false'}
        entries={line.strip() for line in manual.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')}
        if not entries.issubset(allowed):raise ValueError('usb-manual-test.conf has custom rules. Review it manually; refusing to erase them.')
    if not (boot/'config.txt').is_file():raise ValueError('No Raspberry Pi boot config.txt found')


def configure(boot, etc, backup):
    boot,etc,backup=map(Path,(boot,etc,backup));changes=[]
    def write(path,text):
        old=path.read_text() if path.exists() else None
        if old==text:return
        if path.exists():
            saved=backup/str(path).lstrip('/');saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,saved)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);changes.append(str(path))
    validate(boot,etc)
    manual=etc/'modprobe.d/usb-manual-test.conf'
    config=boot/'config.txt'
    if not config.is_file():raise ValueError('No Raspberry Pi boot config.txt found')
    write(config,overlay_config(config.read_text()))
    cmdline=boot/'cmdline.txt'
    if cmdline.is_file():
        value=cmdline.read_text()
        if re.search(r'module_blacklist=[^\s]*(?:dwc2|raw_gadget)',value):write(cmdline,unblock_cmdline(value))
    manual=etc/'modprobe.d/usb-manual-test.conf'
    if manual.exists():
        saved=backup/str(manual).lstrip('/');saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(manual,saved)
        manual.unlink();changes.append(str(manual))
    write(etc/'modules-load.d/skylanders.conf','dwc2\nraw_gadget\n')
    return changes


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot',required=True,type=Path)
    parser.add_argument('--backup',required=True,type=Path)
    parser.add_argument('--etc',type=Path,default=Path('/etc'))
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if args.validate_only:
        validate(args.boot,args.etc)
        print('Boot configuration preflight passed.')
        raise SystemExit(0)
    changed=configure(args.boot,args.etc,args.backup)
    if changed:
        (args.backup/'reboot-required').touch()
        print('Updated boot/module configuration; reboot required. Backups:',args.backup)
    else:print('Boot/module configuration already correct.')
