import importlib.util
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
boot=module('configure_boot');packager=module('package_release')
class TestInstallation(unittest.TestCase):
    def test_overlay_idempotent_preserves_other_models(self):
        source='dtparam=audio=on\ndtoverlay=dwc2,dr_mode=host\n[cm5]\ndtoverlay=dwc2,dr_mode=host\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n'
        fixed=boot.overlay_config(source)
        self.assertEqual(fixed.count('dtoverlay=dwc2,dr_mode=peripheral'),1)
        self.assertIn('[cm5]\ndtoverlay=dwc2,dr_mode=host',fixed)
        self.assertEqual(boot.overlay_config(fixed),fixed)
    def test_unblock_only_owned_modules(self):
        self.assertEqual(boot.unblock_cmdline('console=tty1 module_blacklist=foo,dwc2,raw_gadget,bar rootwait'),
                         'console=tty1 module_blacklist=foo,bar rootwait\n')
    def test_backup_remove_known_block_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=root/'boot';e=root/'etc';backup=root/'backup'
            b.mkdir();(e/'modprobe.d').mkdir(parents=True)
            original='[all]\ndtoverlay=dwc2\n';(b/'config.txt').write_text(original)
            (b/'cmdline.txt').write_text('rootwait module_blacklist=raw_gadget\n')
            manual=e/'modprobe.d/usb-manual-test.conf';manual.write_text('blacklist dwc2\ninstall dwc2 /bin/false\n')
            self.assertTrue(boot.configure(b,e,backup));self.assertFalse(manual.exists())
            self.assertEqual((backup/str(b/'config.txt').lstrip('/')).read_text(),original)
            self.assertEqual((e/'modules-load.d/skylanders.conf').read_text(),'dwc2\nraw_gadget\n')
            self.assertEqual(boot.configure(b,e,backup),[])
    def test_custom_rules_fail_before_boot_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=root/'boot';e=root/'etc';b.mkdir();(e/'modprobe.d').mkdir(parents=True)
            (b/'config.txt').write_text('dtparam=audio=on\n')
            (e/'modprobe.d/usb-manual-test.conf').write_text('install dwc2 /custom/script\n')
            with self.assertRaises(ValueError):boot.configure(b,e,root/'backup')
            self.assertEqual((b/'config.txt').read_text(),'dtparam=audio=on\n')
    def test_source_zip_has_no_private_data_or_binaries_and_keeps_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            for name in ('install.sh','README.md','selection.json','.env','device-mode.json','stray.bin','figures/Spyro.bin','figures/.gitkeep','tests/fixture.dump','usb/raw-bridge','vendor/raw_gadget/raw_gadget.ko','tools/__pycache__/x.pyc','.github/workflows/ci.yml'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test')
            out=packager.package(Path(tmp)/'source.zip',root)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(set(z.namelist()),{'skylanders-zero/install.sh','skylanders-zero/README.md','skylanders-zero/figures/.gitkeep','skylanders-zero/.github/workflows/ci.yml'})
                self.assertTrue(z.getinfo('skylanders-zero/install.sh').external_attr>>16 & 0o111)
    def test_dry_run_needs_no_pi_or_root(self):
        r=subprocess.run(['bash',str(ROOT/'install.sh'),'--dry-run'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('No changes made',r.stdout)
    def helper(self,present):
        with tempfile.TemporaryDirectory() as tmp:
            commands=Path(tmp)/'commands';commands.mkdir();log=Path(tmp)/'calls'
            for name,body in {'uname':'echo skylanders-test-kernel','modinfo':'exit '+('0' if present else '1'),'apt-get':f'echo apt >> "{log}"\nexit 1'}.items():
                p=commands/name;p.write_text('#!/bin/bash\n'+body+'\n');p.chmod(0o755)
            r=subprocess.run(['bash',str(ROOT/'tools/install_raw_gadget.sh')],capture_output=True,text=True,
                             env=dict(os.environ,PATH=str(commands)+':'+os.environ['PATH']))
            return r,log.exists()
    def test_existing_module_needs_no_build(self):
        r,apt=self.helper(True);self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(apt)
    def test_missing_headers_fail_without_full_kernel_build(self):
        r,apt=self.helper(False);self.assertNotEqual(r.returncode,0);self.assertTrue(apt)
        self.assertIn('No full-kernel build',r.stderr)
    def test_legacy_upgrade_preserves_status_and_startup(self):
        import ast
        upgrade=module('upgrade_ui')
        legacy="""from portal import Portal
@app.get('/api/state')
def state():
    files=[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(DATA.iterdir()) if p.is_file() and p.suffix.lower() in ('.bin','.dump','.dmp','.sky') and p.stat().st_size==1024]
    return jsonify(files=files, slots=portal.snapshot(), usb_connected=bool(portal.hid), counters=dict(portal.stats))
if __name__=='__main__':
    worker=threading.Thread(target=serve,args=(portal,stop),daemon=True)
    worker.start()
    app.run(host='0.0.0.0',port=8080,threaded=True,use_reloader=False)
"""
        updated=upgrade.patch_app(legacy)
        def state(text):
            node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='state')
            return ast.get_source_segment(text,node)
        self.assertEqual(state(legacy),state(updated))
        marker="if __name__=='__main__':"
        self.assertEqual(legacy[legacy.index(marker):],updated[updated.index(marker):])
        self.assertEqual(upgrade.patch_app(updated),updated)
    def test_git_ignore_blocks_dump_extensions(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copy2(ROOT/'.gitignore',root/'.gitignore')
            subprocess.run(['git','init','-q',str(root)],check=True)
            names=['Spyro.bin','Tree.BIN','Tag.DuMp','secret.sky','selection.json','.env','figures/a.bin']
            result=subprocess.run(['git','check-ignore','--no-index',*names],cwd=root,capture_output=True,text=True)
            self.assertEqual(set(result.stdout.splitlines()),set(names))
    def test_vendor_hashes(self):
        r=subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=ROOT/'vendor/raw_gadget',capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
