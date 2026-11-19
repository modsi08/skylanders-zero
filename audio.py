# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional local ALSA playback: signed 16-bit LE, mono, 8000 Hz.
Bounded queue ensures audio cannot block the USB control handler.
"""
import queue
import subprocess
import threading
import logging

class Audio:
    def __init__(self,device,stop):
        self.queue=queue.Queue(maxsize=512);self.dropped=0;self.error=None
        self.device=device;self.stop=stop
        threading.Thread(target=self.run,daemon=True).start()
    def feed(self,data):
        try: self.queue.put_nowait(data)
        except queue.Full: self.dropped+=len(data)
    def run(self):
        proc=None
        try:
            proc=subprocess.Popen(['aplay','-q','-D',self.device,'-t','raw','-f','S16_LE','-c','1','-r','8000'],stdin=subprocess.PIPE)
            while not self.stop.is_set():
                try: data=self.queue.get(timeout=.1)
                except queue.Empty: continue
                proc.stdin.write(data);proc.stdin.flush()
        except (OSError,BrokenPipeError) as exc:
            self.error=str(exc);logging.exception('Portal audio unavailable')
        finally:
            if proc:
                proc.terminate()
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired: proc.kill();proc.wait()
