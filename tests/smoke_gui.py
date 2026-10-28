r"""Run manually: .venv\Scripts\python.exe tests/smoke_gui.py"""
import sys
import threading
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.window import Window
from services.workers import analyze
from services.core import FLAGS

root=Path(__file__).resolve().parents[1]
scratch=root/'work'/'smoke'
scratch.mkdir(parents=True,exist_ok=True)
subprocess.run(['C:/ffmpeg/bin/ffmpeg.exe','-y','-f','lavfi','-i','color=c=blue:s=640x360:r=24','-t','2','-c:v','libx264',str(scratch/'sample.mp4')],check=True,capture_output=True,**FLAGS)
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(scratch)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/sample.mp4'
info=analyze(str(root/'bin'/'yt-dlp.exe'),url)
assert info['title']
app=QApplication([])
w=Window(); w.show()
w.url.setText(url); w.title.setText('Test locale autorizzato'); w.directory.setText(str(scratch/'downloads')); w.authorized.setChecked(True)
original=w.settings.copy()
done=False

def poll():
    global done
    if not w.jobs and w.versions_ok:
        w.add_job(); w.start_queue()
    if w.jobs and w.jobs[0]['state']=='Completato':
        assert list((scratch/'downloads').glob('*.mp4'))
        w.grab().save(str(root/'Verifica-interfaccia.png'))
        done=True; w.settings=original; w.close(); app.quit()
    elif w.jobs and w.jobs[0]['state'].startswith('Errore'):
        raise RuntimeError(w.jobs[0]['state'])

timer=QTimer(); timer.timeout.connect(poll); timer.start(200)
QTimer.singleShot(60000,app.quit)
app.exec(); server.shutdown()
assert done, 'GUI smoke test non completato'
print('PASS: metadati locali, GUI, verifica strumenti, coda, download MP4, screenshot')
