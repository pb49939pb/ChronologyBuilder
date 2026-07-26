# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['easyocr']
hiddenimports += collect_submodules('docx')


a = Analysis(
    ['/Users/patrickbaldwin/Documents/Repos/LawFirmAgent/webapp/app.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/patrickbaldwin/Documents/Repos/LawFirmAgent/prompts', 'prompts'), ('/Users/patrickbaldwin/Documents/Repos/LawFirmAgent/webapp/templates', 'templates'), ('/Users/patrickbaldwin/Documents/Repos/LawFirmAgent/webapp/static', 'static'), ('/Users/patrickbaldwin/Documents/Repos/LawFirmAgent/webapp/license_public_key.pem', '.'), ('/Users/patrickbaldwin/.EasyOCR/model', 'easyocr_models')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chronology-builder-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='chronology-builder-backend',
)
