r"""Manual end-to-end test: .venv\Scripts\python.exe tests/smoke_gui.py.
Uses a synthetic video on localhost and isolated settings, queue and history.
"""
import sys
import threading
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import gui.window as gui
import config.settings as config
from config.i18n import t
from services.core import FLAGS, find_ffmpeg

root = Path(__file__).resolve().parents[1]
scratch = root / 'work' / 'smoke-redesign'
scratch.mkdir(parents=True, exist_ok=True)
ffmpeg = find_ffmpeg('')
subprocess.run([ffmpeg, '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=640x360:r=24',
                '-t', '2', '-c:v', 'libx264', str(scratch / 'sample.mp4')],
               check=True, capture_output=True, **FLAGS)
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(scratch)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}/sample.mp4'
app = QApplication([])
settings = config.DEFAULTS | {'language': 'it', 'auto_update': False, 'ffmpeg': ffmpeg}
with patch.object(config, 'ROOT', scratch), patch.object(gui, 'ROOT', scratch), \
        patch.object(gui, 'load', return_value=settings), \
        patch.object(gui, 'load_queue', return_value=[]), \
        patch.object(gui, 'load_history', return_value=[]):
    w = gui.Window()
    w.show()
    w.url.setText(url)
    w.directory.setText(str(scratch / 'downloads'))
    w.subs_check.setChecked(False)
    w.analyze_btn.click()
    state = {'started': False, 'done': False, 'error': None}

    def poll():
        if w.title_input.text() and w.versions_ok and not state['started']:
            state['started'] = True
            w.add_button.click()
            w._start_queue()
        if w.jobs and w.jobs[0]['state'] == t('completed') and not w.tasks and w.current is None:
            assert list((scratch / 'downloads').glob('*.mp4'))
            state['done'] = True
            app.quit()
        elif w.jobs and w.jobs[0]['state'] in (t('error_log'), t('error_start')):
            state['error'] = w.jobs[0]['state']
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(100)
    QTimer.singleShot(45000, app.quit)
    app.exec()
    timer.stop()
    if w.process.state() != w.process.ProcessState.NotRunning:
        w.process.kill()
        w.process.waitForFinished(3000)
    for task in w.tasks[:]:
        task.wait()
    app.processEvents()
    w.close()
server.shutdown()
assert state['done'], state['error'] or 'GUI smoke test timed out'
print('PASS: local analysis, tools, queue, MP4 download and completion; isolated user data')
