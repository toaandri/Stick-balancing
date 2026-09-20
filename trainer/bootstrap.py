"""Explicit application import root for the isolated, private Python runtime."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    from multiprocessing import freeze_support
    freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == 'desktop':
        del sys.argv[1]
        from trainer.desktop import main
    elif len(sys.argv) > 1 and sys.argv[1] == 'evaluate':
        del sys.argv[1]
        from trainer.evaluate import main
    else:
        from trainer.session import main
    raise SystemExit(main())
