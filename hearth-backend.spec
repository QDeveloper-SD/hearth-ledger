# PyInstaller spec: one-folder build of the Hearth backend.
# Build: .venv/bin/pyinstaller --noconfirm --distpath build/pyinstaller --workpath build/pyi-work hearth-backend.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("backend")
    + collect_submodules("argon2")
    + collect_submodules("reportlab")
    + collect_submodules("openpyxl")
    + collect_submodules("python_multipart")
    + ["_cffi_backend", "httptools", "websockets", "pydantic_settings", "ulid", "multipart"]
)
datas = collect_data_files("reportlab") + collect_data_files("pydantic")

a = Analysis(["backend_entry.py"], pathex=["."], hiddenimports=hidden, datas=datas,
             excludes=["tkinter", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="hearth-backend", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="hearth-backend")
