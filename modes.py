# SPDX-License-Identifier: GPL-3.0-or-later
"""Exclusive backend ownership; controller commands are configured locally only."""
import json
import os
import signal
import subprocess
import threading
from pathlib import Path
from transport import serve

class Modes:
    def __init__(self, portal, path, controller_command=None, prepare=None):
        self.portal=portal
        self.path=Path(path)
        self.command=controller_command
        self.prepare=prepare or (lambda: subprocess.run(
            ["/bin/bash", str(Path(__file__).parent/"setup-gadget.sh")], check=True))
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.worker=None
        self.mode="idle"
        self.error=None

    def snapshot(self):
        with self.lock:
            return dict(mode=self.mode, mode_error=self.error,
                        backend_running=bool(self.worker and self.worker.is_alive()),
                        controller_available=bool(self.command),
                        controller_note="8BitDo Pro 2 translation and PS button support are not implemented in this build.")

    def startup(self):
        try:
            requested=json.loads(self.path.read_text())["mode"]
        except FileNotFoundError:
            requested="portal"
        except (ValueError, KeyError, TypeError):
            requested="idle"
            self.error="Invalid saved mode; USB left idle"
        try:
            self.switch(requested)
        except (ValueError, RuntimeError, OSError) as exc:
            self.mode="idle";self.error=str(exc)

    def persist(self, mode):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        with temp.open("w") as f:
            json.dump({"mode":mode},f);f.flush();os.fsync(f.fileno())
        os.replace(temp,self.path)
        fd=os.open(self.path.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def switch(self, mode):
        if mode not in ("portal","controller","idle"):
            raise ValueError("Select portal, controller or idle")
        if mode=="controller" and not self.command:
            raise ValueError("Controller backend unavailable: Pro 2 support still needs development")
        with self.lock:
            if mode==self.mode and (mode=="idle" or self.worker and self.worker.is_alive()):
                self.persist(mode)
                return
            self.stop.set()
            if self.worker:
                self.worker.join(timeout=8)
                if self.worker.is_alive():
                    raise RuntimeError("Previous USB backend did not stop; refusing to start another")
            self.portal.save_all()
            self.mode="idle"
            self.worker=None
            self.error=None
            # Persist idle before attempting the next backend; failed transitions boot idle.
            self.persist("idle")
            if mode=="idle": return
            try:
                if mode=="portal": self.prepare()
                self.stop=threading.Event()
                self.mode=mode
                self.persist(mode)
                target=serve if mode=="portal" else self.controller
                args=(self.portal,self.stop) if mode=="portal" else (self.stop,)
                self.worker=threading.Thread(target=target,args=args,daemon=True)
                self.worker.start()
            except Exception as exc:
                self.mode="idle";self.error=str(exc);self.persist("idle")
                raise RuntimeError(str(exc)) from exc

    def controller(self, stop):
        proc=None
        try:
            proc=subprocess.Popen(self.command,start_new_session=True)
            while not stop.wait(.2):
                if proc.poll() is not None:
                    self.error=f"Controller backend exited with code {proc.returncode}; select Idle before retrying"
                    break
        except Exception as exc:
            self.error=str(exc)
        finally:
            if proc:
                # Backends must stay in the foreground. Stop their entire process group.
                try: os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                # Also terminate descendants if the foreground parent exited first.
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()

    def close(self):
        with self.lock:
            self.stop.set()
            if self.worker: self.worker.join(timeout=8)
            self.portal.save_all()


def controller_command():
    value=os.environ.get("SKYLANDERS_CONTROLLER_COMMAND")
    if not value: return None
    command=json.loads(value)
    if not isinstance(command,list) or not command or any(not isinstance(v,str) or not v for v in command):
        raise ValueError("SKYLANDERS_CONTROLLER_COMMAND must be a JSON array of arguments")
    if not Path(command[0]).is_absolute():
        raise ValueError("Controller executable must use an absolute path")
    return command
