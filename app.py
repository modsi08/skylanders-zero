from selection import install_selection_routes
from identity_api import install_identity_routes
import os, threading, logging, signal
from modes import Modes, controller_command
from audio import Audio
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
from portal import Portal

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('SKYLANDERS_DATA', str(ROOT/'figures')))
DATA.mkdir(parents=True, exist_ok=True)
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=2*1024*1024
portal=Portal(str(DATA))
TOKEN=os.environ.get('SKYLANDERS_TOKEN', '')
stop=threading.Event()
audio=None
modes=None

@app.before_request
def auth():
    if TOKEN and request.headers.get('X-Portal-Token') != TOKEN and request.args.get('token') != TOKEN:
        # Browser page is accessible on LAN; writes require token when configured.
        if request.method!='GET': return jsonify(error='Unauthorized'),401

def payload():
    value=request.get_json(silent=True)
    return value if isinstance(value,dict) else {}

@app.get('/')
def index(): return render_template('index.html')
@app.get('/api/state')
def state():
    files=[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(DATA.iterdir()) if p.is_file() and p.suffix.lower() in ('.bin','.dump','.dmp','.sky') and p.stat().st_size==1024]
    return jsonify(**(modes.snapshot() if modes else dict(mode="portal",controller_available=False,mode_error=None,controller_note="Pro 2 backend not installed")), files=files, slots=portal.snapshot(), usb_connected=bool(portal.hid), usb_error=portal.last_error, counters=dict(portal.stats), audio_enabled=bool(portal.audio_sink), audio_error=audio.error if audio else None)

@app.post('/api/mode')
def set_mode():
    if modes is None: return jsonify(error='Mode manager not running'),503
    try: modes.switch(payload().get('mode'))
    except ValueError as exc: return jsonify(error=str(exc)),400
    except (RuntimeError,OSError) as exc: return jsonify(error=str(exc)),503
    return jsonify(ok=True,**modes.snapshot())

@app.post('/api/upload')
def upload():
    f=request.files.get('file')
    if not f: return jsonify(error='Select a file'),400
    name=secure_filename(f.filename or '')
    if not name or Path(name).suffix.lower() not in ('.bin','.dump','.dmp','.sky'):
        return jsonify(error='Supported: .bin, .dump, .dmp, .sky'),400
    data=f.read(1025)
    if len(data)!=1024: return jsonify(error='Skylander dump must be 1024 bytes'),400
    if (DATA/name).exists(): return jsonify(error='File already exists; rename first'),409
    with portal.lock:
        try:
            with open(DATA/name,'xb') as out:
                out.write(data);out.flush();os.fsync(out.fileno())
        except FileExistsError: return jsonify(error='File already exists'),409
    return jsonify(ok=True,name=name)
@app.post('/api/load')
def load():
    if modes and modes.snapshot()['mode']!='portal': return jsonify(error='Select Portal mode first'),409
    p=payload()
    try: i=portal.load(p.get('name',''), None if p.get('slot') is None else int(p['slot'])-1)
    except (ValueError,TypeError,FileNotFoundError) as exc: return jsonify(error=str(exc)),400
    portal.send_status()
    return jsonify(ok=True,slot=i+1)
@app.post('/api/unload')
def unload():
    p=payload()
    try: portal.unload(int(p['slot'])-1)
    except (ValueError,TypeError,KeyError) as exc: return jsonify(error=str(exc)),400
    portal.send_status()
    return jsonify(ok=True)
@app.post('/api/save')
def save():
    portal.save_all()
    return jsonify(ok=True)
@app.get('/api/download/<name>')
def download(name):
    if name!=os.path.basename(name) or not (DATA/name).is_file():return jsonify(error='Not found'),404
    with portal.lock:
        portal.save_all()
        return send_file(DATA/name,as_attachment=True)
@app.post('/api/delete')
def delete():
    name=(payload()).get('name','')
    if not isinstance(name,str) or name!=os.path.basename(name) or not name:return jsonify(error='Invalid name'),400
    if any(s['file']==name for s in portal.snapshot()):return jsonify(error='Unload this figure first'),409
    p=DATA/name
    if not p.is_file():return jsonify(error='Not found'),404
    with portal.lock:
        if any(s['file']==name for s in portal.snapshot()): return jsonify(error='Unload this figure first'),409
        p.unlink()
    return jsonify(ok=True)

install_identity_routes(app, DATA)

install_selection_routes(app, DATA, portal, lambda: globals().get('modes') is None or modes.snapshot()['mode']=='portal')

if __name__=='__main__':
    logging.basicConfig(level=os.environ.get('SKYLANDERS_LOG_LEVEL','INFO'))
    device=os.environ.get('SKYLANDERS_AUDIO_DEVICE')
    if device:
        audio=Audio(device,stop);portal.audio_sink=audio.feed
    try: command=controller_command()
    except ValueError as exc:
        logging.error('Controller configuration: %s',exc);command=None
    modes=Modes(portal,os.environ.get('SKYLANDERS_MODE_FILE',str(ROOT/'device-mode.json')),command)
    modes.startup()
    def shutdown(signum,frame):
        stop.set();modes.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    app.run(host='0.0.0.0',port=8080,threaded=True,use_reloader=False)
