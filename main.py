import sys
from PySide6.QtWidgets import QApplication

def main():
    from gui.window import Window
    from config.version import VERSION
    app = QApplication(sys.argv)
    app.setApplicationName('Movie Downloader')
    app.setApplicationVersion(VERSION)
    window = Window()
    window.show()
    return app.exec()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        import traceback
        import os
        from pathlib import Path
        report = Path(os.environ.get('LOCALAPPDATA', '.')) / 'MovieDownloader' / 'startup-error.log'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(traceback.format_exc(), encoding='utf-8')
        raise
