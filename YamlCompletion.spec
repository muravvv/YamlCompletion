# -*- mode: python ; coding: utf-8 -*-

import os
import sys

site_packages = next(p for p in sys.path if 'site-packages' in p)

a = Analysis(
    ['YamlCompletion.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(site_packages,"litellm", "*.json"), "litellm"),
        (os.path.join(site_packages,"litellm/litellm_core_utils/tokenizers", "anthropic_tokenizer.json"), "litellm/litellm_core_utils/tokenizers"),
        (os.path.join(site_packages,"litellm/containers", "endpoints.json"), "litellm/containers"),
        (os.path.join(site_packages,"litellm/llms/openai_like", "providers.json"), "litellm/llms/openai_like"),
    ],
    hiddenimports=['litellm.litellm_core_utils.tokenizers', 'tiktoken_ext.openai_public'],
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
    name='YamlCompletion',
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
    name='YamlCompletion',
)
