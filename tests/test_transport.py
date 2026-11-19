import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from portal import Portal
from transport import serve

class TestTransport(unittest.TestCase):
    def test_supervisor_exchanges_commands_and_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);log=root/'packets.json';script=root/'fake_bridge.py'
            script.write_text('''import os,sys,json
os.write(1,b'\\x03\\x00\\x01\\x01R')
packets=[]
while True:
    packet=sys.stdin.buffer.read(32)
    if len(packet)!=32:break
    packets.append(packet.hex())
    with open(sys.argv[1],'w') as f:json.dump(packets,f)
    os.write(1,b'\\x04\\x00')
''')
            real_popen=subprocess.Popen
            def fake_popen(args,**kwargs):
                return real_popen([sys.executable,str(script),str(log)],**kwargs)
            p=Portal(folder);stop=threading.Event()
            with patch('transport.udc_names',return_value=('dummy','dummy')),patch('transport.subprocess.Popen',side_effect=fake_popen):
                thread=threading.Thread(target=serve,args=(p,stop));thread.start()
                try:
                    end=time.monotonic()+2
                    while time.monotonic()<end:
                        if log.exists():
                            try:
                                packets=json.loads(log.read_text())
                                if len(packets)>=3:break
                            except json.JSONDecodeError:pass
                        time.sleep(.01)
                    else:self.fail('No completed bridge exchange')
                    self.assertEqual(bytes.fromhex(packets[0])[:3],b'R\x02\x18')
                    self.assertEqual(bytes.fromhex(packets[1])[0],ord('S'))
                    self.assertIsNotNone(p.hid)
                finally:
                    stop.set();thread.join(timeout=3)
                self.assertFalse(thread.is_alive());self.assertIsNone(p.hid)

if __name__=='__main__':unittest.main()
