import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from portal import Portal
from transport import Frames

class TestPortal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/'figure.bin';self.file.write_bytes(bytes(1024))
        self.p=Portal(self.temp.name)
    def status(self):
        packet=self.p.command(b'S');self.p.transmitted(packet);return packet
    def test_startup(self):
        self.assertEqual(self.p.command(b'R')[:3],b'R\x02\x18')
        self.assertEqual(self.p.command(b'A\x01')[:4],b'A\x01\xff\x77')
        self.assertEqual(self.p.command(b'J'),b'J'+bytes(31))
        self.assertEqual(self.p.command(b'M\x01')[:4],b'M\x01\x00\x19')
        self.assertEqual(self.p.command(b'S')[6],1)
    def test_transitions_only_on_completion(self):
        self.p.load('figure.bin');self.p.connected(object())
        for _ in range(10): self.assertEqual(self.p.command(b'S')[1]&3,3)
        for _ in range(5): self.assertEqual(self.status()[1]&3,3)
        self.assertEqual(self.status()[1]&3,1)
        self.p.unload(0)
        for _ in range(5): self.assertEqual(self.status()[1]&3,2)
        self.assertEqual(self.status()[1]&3,0)
        self.assertIsNone(self.p.slots[0])
    def test_stale_status_does_not_advance_new_transition(self):
        self.p.load('figure.bin');self.p.connected(object())
        old=self.p.command(b'S');self.p.unload(0);self.p.transmitted(old)
        self.assertEqual(self.p.remaining[0],5)
    def test_all_slots_and_counter_wrap(self):
        for i in range(16):
            (Path(self.temp.name)/f'{i}.bin').write_bytes(bytes(1024));self.p.load(f'{i}.bin',i)
        self.assertEqual(self.p.command(b'S')[1:5],b'\xff'*4)
        self.p.seq=255;self.status();self.assertEqual(self.p.seq,0)
    def test_roundtrip_including_early_blocks(self):
        self.p.load('figure.bin')
        for block in (0,3,4,63):
            self.assertEqual(self.p.command(bytes([ord('W'),0x10,block])+bytes(range(16)))[:3],bytes([ord('W'),0x10,block]))
            self.assertEqual(self.p.command(bytes([ord('Q'),0x10,block]))[3:19],bytes(range(16)))
            self.assertEqual(self.file.read_bytes()[block*16:block*16+16],bytes(range(16)))
        self.assertEqual(Path(str(self.file)+'.original').read_bytes(),bytes(1024))
        self.p.unload(0);self.p.load('figure.bin')
        self.assertEqual(self.p.command(b'Q\x10\x3f')[3:19],bytes(range(16)))
    def test_write_during_removal_persists(self):
        self.p.load('figure.bin');self.p.connected(object());self.p.unload(0)
        self.p.command(b'W\x10\x04'+bytes(range(16)))
        for _ in range(5): self.status()
        self.assertEqual(self.file.read_bytes()[64:80],bytes(range(16)))
    def test_absent_out_of_range_and_short_requests(self):
        self.assertEqual(self.p.command(b'Q\x1f\x04')[:3],b'Q\x0f\x04')
        self.p.load('figure.bin')
        self.assertEqual(self.p.command(b'W\x10\xff'+bytes(16))[:3],b'W\x00\xff')
        for data in (b'A',b'M',b'Q',b'W\x00\x04'):
            self.assertIsNone(self.p.command(data))
    def test_failed_save_never_acks_success(self):
        self.p.load('figure.bin')
        with patch.object(self.p,'save',side_effect=OSError('disk full')):
            reply=self.p.command(b'W\x10\x04'+bytes(range(16)))
        self.assertEqual(reply[1],0);self.assertEqual(self.p.slots[0]['data'][64:80],bytes(16))
    def test_audio_not_parsed_as_command(self):
        captured=[];self.p.audio_sink=captured.append
        self.p.command(b'M\x01')
        pcm=b'W'+bytes(31)
        self.assertIsNone(self.p.command(pcm,'interrupt'))
        self.assertEqual(captured,[pcm]);self.assertEqual(self.p.stats['audio_bytes'],32)
        self.assertEqual(self.p.command(b'Q\x10\x04','control')[0],ord('Q'))
    def test_reconnect_reannounces_and_offline_unload(self):
        self.p.load('figure.bin');self.p.connected(object())
        for _ in range(5): self.status()
        self.p.disconnected();self.p.connected(object())
        self.assertEqual(self.p.status[0],3)
        self.p.disconnected();self.p.unload(0);self.assertIsNone(self.p.slots[0])
    def test_reject_duplicate_and_bad_file(self):
        self.p.load('figure.bin')
        with self.assertRaises(ValueError):self.p.load('figure.bin')
        with self.assertRaises(ValueError):self.p.load('../figure.bin')
        with self.assertRaises(ValueError):self.p.load([],0)
        (Path(self.temp.name)/'bad.bin').write_bytes(bytes(1025))
        with self.assertRaises(ValueError):self.p.load('bad.bin')
    def test_bridge_fragmentation(self):
        frames=Frames()
        self.assertEqual(frames.feed(b'\x01\x03Q'),[])
        self.assertEqual(frames.feed(b'\x10\x04\x03\x00\x04\x00'),[(1,b'Q\x10\x04'),(3,b''),(4,b'')])
        with self.assertRaises(ValueError):frames.feed(b'\x01\xff')

if __name__=='__main__':unittest.main()
