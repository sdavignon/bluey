"""Entry point for PyInstaller, which cannot run package-relative app.py directly."""
from bluey.app import main

if __name__ == '__main__':
    main()
