# Build with: python -m PyInstaller --noconfirm DesktopPetTemplate.spec
from pathlib import Path
import sys

root = Path(SPECPATH).resolve()
datas = [(str(root / 'characters'), 'characters'), (str(root / 'app/assets'), 'assets')]
tcl_base = Path(sys.base_prefix) / 'tcl'
if (tcl_base / 'tcl8.6/init.tcl').exists():
    datas.extend([(str(tcl_base / 'tcl8.6'), '_tcl_data'),(str(tcl_base / 'tk8.6'), '_tk_data')])
a = Analysis([str(root / 'run.py')],pathex=[str(root / 'app')],datas=datas,
             hookspath=[str(root / 'hooks')],
             hiddenimports=['desktop_pet','character_pack','pack_validation','glass_ui','glass_popup','speech_card','window_placement','keyboard_activity','activity_logic','pystray._win32','PIL._tkinter_finder'],excludes=['openai'],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='DesktopPetTemplate',console=False,debug=False,strip=False,upx=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='DesktopPetTemplate')
