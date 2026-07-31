# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
import os

block_cipher = None

# Collect all data and hidden imports for packages
fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all('fastapi')
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all('uvicorn')
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all('pydantic')
cryptography_datas, cryptography_binaries, cryptography_hiddenimports = collect_all('cryptography')
rich_datas, rich_binaries, rich_hiddenimports = collect_all('rich')

# Add static web assets
current_dir = os.getcwd()
static_dir = os.path.join(current_dir, 'static')
additional_datas = []

if os.path.exists(static_dir):
    # Add all static files
    additional_datas.append((static_dir, 'static'))

# Add the iTerm2 profiles shipped with Connectify
profiles_dir = os.path.join(current_dir, 'profiles')
if os.path.exists(profiles_dir):
    additional_datas.append((profiles_dir, 'profiles'))

a = Analysis(
    ['main.py', 'api_server.py'],
    pathex=[],
    binaries=[] + fastapi_binaries + uvicorn_binaries + pydantic_binaries + cryptography_binaries + rich_binaries,
    datas=[] + fastapi_datas + uvicorn_datas + pydantic_datas + cryptography_datas + rich_datas + additional_datas,
    hiddenimports=[
        'importlib.metadata',
        'importlib_metadata',
        # FastAPI dependencies
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.responses',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'uvicorn',
        'uvicorn.server',
        'uvicorn.config',
        'uvicorn.main',
        'starlette',
        'starlette.applications',
        'starlette.routing',
        'starlette.responses',
        'starlette.staticfiles',
        'httpx',
        'typing_extensions',
        'pydantic',
        'pydantic.dataclasses',
        'pydantic.types',
        'email_validator',
        'pkg_resources',
        # Installer UI
        'rich',
        # Credentials vault encryption
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
    ] + fastapi_hiddenimports + uvicorn_hiddenimports + pydantic_hiddenimports + cryptography_hiddenimports + rich_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly exclude user config and backup files/folders
        '.ssh_manager_config.json',
        'backup',
        'backup/*',
        '*.json',  # Exclude any JSON config files
        '.git',
        '.git/*',
        '.venv',
        '.venv/*',
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '.DS_Store',
        'Thumbs.db',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],  # Don't bundle binaries as onefile - causes issues with Python libs
    exclude_binaries=True,  # Fix for Python shared library issues
    name='launch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='launch',
)