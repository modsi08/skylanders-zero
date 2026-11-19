import importlib.util
import tempfile
import unittest
import threading
from unittest.mock import patch
from pathlib import Path
from catalogue import Catalogue, catalogue, library_state
from portal import Portal


def dump(character,variant):
    data=bytearray(1024);data[:4]=b'TEST'
    data[16:19]=character.to_bytes(3,'little')
    data[28:30]=variant.to_bytes(2,'little')
    return data


class TestCatalogue(unittest.TestCase):
    def test_slow_library_scan_does_not_block_game_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'figure.bin').write_bytes(dump(112,0x1206))
            portal=Portal(folder);portal.load('figure.bin')
            entered=threading.Event();release=threading.Event();answered=threading.Event()
            original=catalogue.identify_file
            result=[]
            def slow(path):
                entered.set()
                if not release.wait(5): raise RuntimeError('Test scan not released')
                return original(path)
            def command():
                result.append(portal.command(b'Q\x10\x01'))
                answered.set()
            with patch.object(catalogue,'identify_file',side_effect=slow):
                scan=threading.Thread(target=library_state,args=(folder,portal))
                scan.start()
                try:
                    self.assertTrue(entered.wait(2))
                    usb=threading.Thread(target=command);usb.start()
                    self.assertTrue(answered.wait(2),'Figure scan blocked USB command handling')
                    self.assertEqual(result[0][:3],b'Q\x10\x01')
                finally:
                    release.set();scan.join(3)
                    if 'usb' in locals():usb.join(3)
    def test_ids_little_endian_and_exact_variant(self):
        f=catalogue.identify(dump(112,0x1206))
        self.assertEqual((f['name'],f['figure_type'],f['element']),('Tree Rex','Giant','Life'))
        gnarly=catalogue.identify(dump(112,0x1602))
        self.assertIn('Gnarly',gnarly['name']);self.assertTrue(gnarly['known_variant'])
        self.assertEqual(catalogue.identify(dump(112,0))['match'],'character_only')
    def test_unknown_variant_never_claims_standard(self):
        f=catalogue.identify(dump(112,65535))
        self.assertEqual(f['figure_type'],'Giant');self.assertFalse(f['known_variant'])
        self.assertEqual(f['variant_name'],'Unknown variant');self.assertIsNone(f['edition_game'])
    def test_unknown_blank_and_24_bit_character(self):
        self.assertEqual(catalogue.identify(bytes(1024))['match'],'unknown')
        f=catalogue.identify(dump(0x10070,0x1206))
        self.assertFalse(f['known_character']);self.assertEqual(f['character_id'],0x10070)
        with self.assertRaises(ValueError):catalogue.identify(bytes(31))
    def test_non_giants_minis_swap_and_later_games(self):
        for c,v,kind in [(100,0x1000,'Regular'),(540,0x3000,'Mini'),(540,0x1000,'Sidekick'),
                         (462,0x3000,'Trap Master'),(601,0x5000,'Sensei'),(3224,0x4000,'Vehicle')]:
            with self.subTest(c=c,v=v):self.assertEqual(catalogue.identify(dump(c,v))['figure_type'],kind)
        for c,half in [(1000,'Bottom'),(2000,'Top')]:
            f=catalogue.identify(dump(c,0x2000));self.assertEqual(f['swap_half'],half)
        self.assertFalse(catalogue.identify(dump(3423,0x4100))['ps3_supported'])
    def test_read_only_header_cache_invalidates_after_write(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'misleading-name.bin';data=dump(112,0x1206);p.write_bytes(data)
            self.assertEqual(catalogue.identify_file(p)['figure_type'],'Giant')
            self.assertEqual(p.read_bytes(),data)
            p.write_bytes(dump(16,0))
            self.assertEqual(catalogue.identify_file(p)['name'],'Spyro')
    def test_slots_use_current_memory_and_dump_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'figure.bin';data=dump(112,0x1206);p.write_bytes(data)
            portal=Portal(folder);portal.load('figure.bin')
            files,slots=library_state(folder,portal)
            self.assertEqual(files[0]['figure']['name'],'Tree Rex')
            self.assertEqual(slots[0]['figure']['name'],'Tree Rex')
            self.assertEqual(p.read_bytes(),data)
            portal.slots[0]['data']=dump(16,0)
            self.assertEqual(library_state(folder,portal)[1][0]['figure']['name'],'Spyro')
    def test_catalogue_has_all_eight_giants_and_no_duplicate_keys(self):
        giants={f['character_id'] for f in catalogue.records.values() if f['figure_type']=='Giant'}
        self.assertEqual(giants,{101,102,104,107,109,110,112,114})
        self.assertGreater(len(catalogue.records),700)
    def test_ui_upgrade_preserves_existing_usb_startup(self):
        spec=importlib.util.spec_from_file_location('upgrade',Path(__file__).parents[1]/'tools/upgrade_ui.py')
        upgrade=importlib.util.module_from_spec(spec);spec.loader.exec_module(upgrade)
        source=(Path(__file__).parents[1]/'app.py').read_text()
        self.assertEqual(upgrade.patch_app(source),source)
        import zipfile
        old=Path(__file__).parents[3]/'downloads/skylanders-zero-prototype.zip'
        if old.exists():
            with zipfile.ZipFile(old) as z:
                legacy=z.read('skylanders-zero/app.py').decode()
            result=upgrade.patch_app(legacy)
            self.assertNotIn('library_state(DATA,portal)',result)
            self.assertIn('install_identity_routes(app, DATA)',result)
            self.assertEqual(legacy[legacy.index("if __name__=='__main__':"):],result[result.index("if __name__=='__main__':"):])
            import ast
            def state_source(text):
                tree=ast.parse(text);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='state')
                return ast.get_source_segment(text,node)
            self.assertEqual(state_source(legacy),state_source(result))

if __name__=='__main__':unittest.main()
