# SPDX-License-Identifier: GPL-3.0-or-later
"""Portal protocol adapted from Alexander Shaffer's GPLv3 Pico implementation.
No USB transport writes take place while the figure lock is held.
"""
import os
import time
import logging
import threading
from collections import Counter

LOG = logging.getLogger(__name__)
SIZE = 1024

class Portal:
    def __init__(self, folder):
        self.folder = folder
        self.lock = threading.RLock()
        self.slots = [None] * 16
        self.status = [0] * 16  # 0 absent, 1 present, 2 removing, 3 adding
        self.remaining = [0] * 16
        self.seq = 0
        self.active = False
        self.hid = None  # set only on SET_CONFIGURATION, never merely on open
        self.last_error = None
        self.stats = Counter()
        self.audio_until = 0
        self.audio_sink = None
        self.wake = threading.Event()

    def snapshot(self):
        with self.lock:
            return [{'slot': i+1, 'file': s['name'] if s else None,
                     'state': self.status[i]} for i,s in enumerate(self.slots)]

    def load(self, filename, slot=None):
        if not isinstance(filename,str) or not filename or filename != os.path.basename(filename):
            raise ValueError('Invalid file')
        with self.lock:
            if any(s and s['name']==filename for s in self.slots):
                raise ValueError('Already loaded')
            if slot is None:
                slot=next((i for i,s in enumerate(self.slots) if s is None),None)
            if not isinstance(slot,int) or not 0<=slot<16:
                raise ValueError('No available slot')
            if self.slots[slot] is not None: raise ValueError('Slot occupied')
            path=os.path.join(self.folder,filename)
            if os.path.islink(path): raise ValueError('Symlink not allowed')
            with open(path,'rb') as f: data=f.read(SIZE+1)
            if len(data)!=SIZE: raise ValueError('File must be exactly 1024 bytes')
            # Keep the initial uploaded dump as a backup, never overwrite it.
            backup=path+'.original'
            if not os.path.exists(backup):
                with open(backup,'xb') as f:
                    f.write(data);f.flush();os.fsync(f.fileno())
            self.slots[slot]={'name':filename,'data':bytearray(data)}
            self.status[slot]=3;self.remaining[slot]=5
            self.wake.set()
            return slot

    def unload(self, slot):
        with self.lock:
            if not isinstance(slot,int) or not 0<=slot<16: raise ValueError('Invalid slot')
            if self.slots[slot] is None: raise ValueError('Empty slot')
            if self.status[slot]==2: return
            self.save(slot)
            if self.hid:
                self.status[slot]=2;self.remaining[slot]=5
            else:
                self.status[slot]=0;self.remaining[slot]=0;self.slots[slot]=None
            self.wake.set()

    def save(self, slot):
        with self.lock:
            if not isinstance(slot,int) or not 0<=slot<16: raise ValueError('Invalid slot')
            entry=self.slots[slot]
            if not entry: return
            dest=os.path.join(self.folder,entry['name']);tmp=dest+'.tmp'
            with open(tmp,'wb') as f:
                f.write(entry['data']);f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
            directory=os.open(self.folder,os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)

    def save_all(self):
        with self.lock:
            for i,s in enumerate(self.slots):
                if s: self.save(i)

    def connected(self, handle):
        with self.lock:
            self.hid=handle;self.last_error=None;self.active=False
            self.seq=0;self.audio_until=0
            for i,s in enumerate(self.slots):
                if self.status[i]==2:
                    self.save(i);self.slots[i]=None;self.status[i]=0;self.remaining[i]=0
                elif s:
                    self.status[i]=3;self.remaining[i]=5

    def disconnected(self):
        with self.lock:
            self.hid=None;self.active=False;self.audio_until=0
            for i,s in enumerate(self.slots):
                if s and self.status[i]==2:
                    self.save(i);self.slots[i]=None;self.status[i]=0;self.remaining[i]=0

    def _status_packet(self):
        with self.lock:
            bits=sum(state<<(i*2) for i,state in enumerate(self.status))
            return b'S'+bits.to_bytes(4,'little')+bytes([self.seq,1])+bytes(25)

    def transmitted(self, packet):
        """Advance only the transitions actually represented in a completed report."""
        if not packet or packet[0]!=ord('S'): return
        with self.lock:
            self.seq=(self.seq+1)&255
            bits=int.from_bytes(packet[1:5],'little')
            for i,state in enumerate(self.status):
                if state in (2,3) and (bits>>(i*2))&3==state:
                    self.remaining[i]-=1
                    if self.remaining[i]<=0:
                        self.status[i]=1 if state==3 else 0
                        if state==2:
                            self.save(i);self.slots[i]=None

    @staticmethod
    def reply(data): return bytes(data).ljust(32,b'\0')

    def command(self,data,source='control'):
        if not data: return None
        with self.lock:
            # Audio is carried over the same interrupt OUT endpoint, not USB Audio Class.
            if source=='interrupt' and len(data)==32 and time.monotonic()<self.audio_until:
                self.stats['audio_bytes']+=32
                self.audio_until=time.monotonic()+0.5
                if self.audio_sink: self.audio_sink(data)
                return None
            cmd=chr(data[0]);self.stats[cmd]+=1
            LOG.debug('RX %s %s',source,data.hex())
            if cmd=='A' and len(data)>=2:
                self.active=bool(data[1]);return self.reply([ord('A'),data[1],0xff,0x77])
            if cmd=='R':
                self.active=True;return self.reply([ord('R'),2,0x18])
            if cmd=='J': return self.reply(b'J')
            if cmd=='M' and len(data)>=2:
                self.audio_until=time.monotonic()+0.5
                return self.reply([ord('M'),data[1],0,0x19])
            if cmd=='S': return self._status_packet()
            if cmd in ('Q','W') and len(data)>=(19 if cmd=='W' else 3):
                slot=data[1]&15;block=data[2];entry=self.slots[slot]
                result=bytearray(32);result[:3]=data[:3]
                if entry is None or block>=64:
                    result[1]=slot  # absent/error: success flag unset
                    self.stats['invalid_block']+=1
                elif cmd=='Q':
                    result[1]=0x10|slot
                    result[3:19]=entry['data'][block*16:(block+1)*16]
                else:
                    old=entry['data'][block*16:(block+1)*16]
                    entry['data'][block*16:(block+1)*16]=data[3:19]
                    try: self.save(slot)
                    except OSError:
                        entry['data'][block*16:(block+1)*16]=old
                        LOG.exception('Save failed; withholding successful write acknowledgement')
                        result[1]=slot;self.stats['save_errors']+=1
                    else: result[1]=0x10|slot;self.stats['saved_blocks']+=1
                return bytes(result)
            if cmd in ('C','L'): return None
            self.stats['unhandled']+=1
            LOG.warning('Unhandled/malformed portal command: %s',data.hex())
            return None

    def send_status(self): self.wake.set()
