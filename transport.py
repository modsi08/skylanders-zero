# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-writer USB supervisor with completion-based slot transitions."""
import os
import select
import subprocess
import time
import logging
from pathlib import Path
from collections import deque

LOG=logging.getLogger(__name__)

class Frames:
    def __init__(self): self.buffer=bytearray()
    def feed(self,data):
        self.buffer.extend(data);result=[]
        while len(self.buffer)>=2:
            kind,n=self.buffer[:2]
            if kind not in (1,2,3,4) or n>64: raise ValueError('Invalid bridge frame')
            if len(self.buffer)<2+n: break
            result.append((kind,bytes(self.buffer[2:2+n])))
            del self.buffer[:2+n]
        return result

def udc_names():
    name=os.environ.get('SKYLANDERS_UDC')
    if not name:
        devices=list(Path('/sys/class/udc').iterdir())
        if len(devices)!=1: raise RuntimeError('Expected one UDC; set SKYLANDERS_UDC explicitly')
        name=devices[0].name
    # Raw Gadget requires the UDC instance name used by dwc2, not the module label.
    uevent=(Path('/sys/class/udc')/name/'uevent').read_text()
    reported=next((line.split('=',1)[1] for line in uevent.splitlines() if line.startswith('USB_UDC_NAME=')),name)
    driver=os.environ.get('SKYLANDERS_UDC_DRIVER',reported)
    return driver,name

def serve(portal,stop):
    root=Path(__file__).resolve().parent
    while not stop.is_set():
        proc=None
        try:
            driver,device=udc_names()
            proc=subprocess.Popen([str(root/'usb/raw-bridge'),driver,device],
                                  stdin=subprocess.PIPE,stdout=subprocess.PIPE,bufsize=0)
            os.set_blocking(proc.stdin.fileno(),False)
            frames=Frames();pending=deque();inflight=None;configured=False;next_status=0
            LOG.info('Raw Gadget started on %s',device)
            while not stop.is_set():
                readable,_,_=select.select([proc.stdout],[],[],0.01)
                if readable:
                    chunk=os.read(proc.stdout.fileno(),4096)
                    if not chunk: raise RuntimeError('USB bridge exited; see SETUP/error logs')
                    for kind,data in frames.feed(chunk):
                        if kind==3:
                            configured=True;portal.connected(proc);next_status=0
                            LOG.info('USB configured by host (game recognition still unverified)')
                        elif kind==4:
                            if inflight is not None: portal.transmitted(inflight)
                            inflight=None
                        else:
                            response=portal.command(data,'control' if kind==1 else 'interrupt')
                            if response is not None: pending.append(response)
                            if len(pending)>256: raise RuntimeError('USB response backlog exceeded')
                if configured and inflight is None:
                    now=time.monotonic()
                    packet=pending.popleft() if pending else None
                    if packet is None and (portal.active or any(s['state'] in (2,3) for s in portal.snapshot())) and now>=next_status:
                        packet=portal._status_packet();next_status=now+0.023
                    if packet is not None:
                        # <= PIPE_BUF, so a nonblocking write is atomic.
                        try: n=os.write(proc.stdin.fileno(),packet)
                        except BlockingIOError: pending.appendleft(packet)
                        else:
                            if n!=32: raise RuntimeError('Short USB bridge write')
                            inflight=packet
        except Exception as exc:
            portal.last_error=str(exc);LOG.warning('USB: %s',exc)
        finally:
            portal.disconnected()
            if proc:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=2)
                    except subprocess.TimeoutExpired: proc.kill();proc.wait()
                proc.stdin.close();proc.stdout.close()
        stop.wait(0.5)
