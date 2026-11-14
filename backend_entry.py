"""PyInstaller entry point: same as `python -m backend`."""
from backend.__main__ import main

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
