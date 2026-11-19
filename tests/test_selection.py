import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from flask import Flask
from portal import Portal
from selection import Selection, install_selection_routes


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'figures';self.folder.mkdir()
        for name in ('Spyro.bin','Tree Rex.bin'):(self.folder/name).write_bytes(bytes(1024))
        self.portal=Portal(str(self.folder));self.selection=Selection(self.folder,self.portal,timeout=.12)
    def test_add_only_stages_and_survives_restart(self):
        self.assertEqual(self.selection.add('Spyro.bin'),1)
        self.assertEqual(self.selection.add('Spyro.bin'),1)
        self.assertEqual(self.selection.add('Tree Rex.bin'),2)
        self.assertTrue(all(s['file'] is None for s in self.portal.snapshot()))
        restored=Selection(self.folder,self.portal)
        self.assertEqual(restored.files[:2],['Spyro.bin','Tree Rex.bin'])
    def test_offline_switch_activates_exactly_one_without_deleting_choices(self):
        self.selection.add('Spyro.bin');self.selection.add('Tree Rex.bin')
        self.selection.activate(1);self.selection.activate(2)
        self.assertEqual([s['file'] for s in self.portal.snapshot() if s['file']],['Tree Rex.bin'])
        self.assertEqual(self.selection.files[:2],['Spyro.bin','Tree Rex.bin'])
        self.selection.activate(2) # idempotent
        self.selection.deactivate()
        self.assertTrue(all(s['file'] is None for s in self.portal.snapshot()))
    def test_connected_switch_waits_for_removal_reports_before_loading_next(self):
        self.selection.timeout=1
        self.selection.add('Spyro.bin');self.selection.add('Tree Rex.bin');self.selection.activate(1)
        self.portal.connected(object())
        stop=threading.Event();counts=[]
        def host():
            while not stop.is_set():
                packet=self.portal.command(b'S')
                states=[(int.from_bytes(packet[1:5],'little')>>(i*2))&3 for i in range(16)]
                counts.append(sum(s!=0 for s in states))
                self.portal.transmitted(packet);time.sleep(.005)
        thread=threading.Thread(target=host);thread.start()
        try:self.selection.activate(2)
        finally:stop.set();thread.join(2)
        self.assertEqual([s['file'] for s in self.portal.snapshot() if s['file']],['Tree Rex.bin'])
        self.assertLessEqual(max(counts),1)
        self.assertEqual(self.selection.files[:2],['Spyro.bin','Tree Rex.bin'])
    def test_timeout_never_loads_second_figure(self):
        self.selection.add('Spyro.bin');self.selection.add('Tree Rex.bin');self.selection.activate(1)
        self.portal.connected(object())
        with self.assertRaises(TimeoutError):self.selection.activate(2)
        self.assertEqual([s['file'] for s in self.portal.snapshot() if s['file']],['Spyro.bin'])
    def test_missing_target_leaves_current_active(self):
        self.selection.add('Spyro.bin');self.selection.add('Tree Rex.bin');self.selection.activate(1)
        (self.folder/'Tree Rex.bin').unlink()
        with self.assertRaises(ValueError):self.selection.activate(2)
        self.assertEqual(self.portal.snapshot()[0]['file'],'Spyro.bin')
    def test_remove_retains_dump_and_original_save(self):
        self.selection.add('Spyro.bin');self.selection.activate(1);self.selection.remove(1)
        self.assertIsNone(self.selection.files[0]);self.assertIsNone(self.portal.snapshot()[0]['file'])
        self.assertTrue((self.folder/'Spyro.bin').is_file())
    def test_full_selection_validation_and_corrupt_store(self):
        for i in range(16):
            name=f'{i}.bin';(self.folder/name).write_bytes(bytes(1024));self.selection.add(name)
        with self.assertRaises(ValueError):self.selection.add('Spyro.bin')
        for slot in (None,0,17,True,'1'):
            with self.assertRaises(ValueError):self.selection.activate(slot)
        self.selection.path.write_text('bad json')
        broken=Selection(self.folder,self.portal);self.assertIsNotNone(broken.error)
        with self.assertRaises(ValueError):broken.add('Spyro.bin')
    def test_simultaneous_activation_requests_stay_single(self):
        self.selection.add('Spyro.bin');self.selection.add('Tree Rex.bin')
        barrier=threading.Barrier(3);errors=[]
        def activate(slot):
            barrier.wait()
            try:self.selection.activate(slot)
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=activate,args=(slot,)) for slot in (1,2)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(2)
        self.assertEqual(errors,[])
        self.assertEqual(sum(s['file'] is not None for s in self.portal.snapshot()),1)
    def test_routes_and_mode_guard(self):
        app=Flask('selection');install_selection_routes(app,self.folder,self.portal,lambda:False)
        c=app.test_client()
        self.assertEqual(len(c.get('/api/selection').json['slots']),16)
        self.assertEqual(c.post('/api/selection/add',json={'name':'Spyro.bin'}).status_code,200)
        self.assertEqual(c.post('/api/selection/activate',json={'slot':1}).status_code,409)
        self.assertEqual(c.post('/api/selection/remove',json={'slot':1}).status_code,200)

if __name__=='__main__':unittest.main()
