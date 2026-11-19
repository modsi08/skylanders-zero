import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from modes import Modes

class Portal:
    def save_all(self): pass

class TestModes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.events=[]
        self.manager=Modes(Portal(),Path(self.temp.name)/'mode.json',prepare=lambda:self.events.append('prepare'))
        self.addCleanup(self.manager.close)
    def backend(self,portal,stop):
        self.events.append('start');stop.wait();self.events.append('stop')
    def test_release_before_restart_and_persist(self):
        with patch('modes.serve',self.backend):
            self.manager.switch('portal');self.manager.switch('idle')
            self.assertEqual(self.events,['prepare','start','stop'])
            self.manager.switch('portal');self.manager.switch('idle')
        other=Modes(Portal(),self.manager.path,prepare=lambda:self.fail('Idle must not load USB'))
        other.startup();self.assertEqual(other.mode,'idle')
    def test_unsupported_controller_keeps_portal_running(self):
        with patch('modes.serve',self.backend):
            self.manager.switch('portal')
            with self.assertRaises(ValueError): self.manager.switch('controller')
            self.assertEqual(self.manager.mode,'portal');self.assertTrue(self.manager.worker.is_alive())
    def test_failed_preparation_stays_idle_across_reboot(self):
        def fail(): raise OSError('USB unavailable')
        self.manager.prepare=fail
        with self.assertRaises(RuntimeError): self.manager.switch('portal')
        self.assertEqual(self.manager.mode,'idle')
        other=Modes(Portal(),self.manager.path,prepare=lambda:self.fail('Must remain idle'))
        other.startup();self.assertEqual(other.mode,'idle')
    def test_live_controller_excludes_portal(self):
        self.manager.command=['/usr/bin/python3','-c','import time; time.sleep(60)']
        self.manager.switch('controller');old=self.manager.worker
        with patch('modes.serve',self.backend):
            self.manager.switch('portal');self.assertFalse(old.is_alive());self.assertTrue(self.manager.worker.is_alive())
    def test_corrupt_saved_mode_never_initializes_usb(self):
        self.manager.path.write_text('invalid json')
        self.manager.prepare=lambda:self.fail('Invalid state must not load USB')
        self.manager.startup();self.assertEqual(self.manager.mode,'idle')

if __name__=='__main__': unittest.main()
