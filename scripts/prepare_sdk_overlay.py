#!/usr/bin/env python3
"""Guard SDK 15 half declarations unsupported by pinned clang on Intel.
The system SDK is never modified. Only declarations for macOS 15 APIs that
CEF 104 does not use are hidden when the compiler lacks the Float16 type.
"""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sdk = Path('/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk')
source = sdk / 'usr/include/math.h'
text = source.read_text()
start = text.index('/* half precision math functions */')
end = text.index('\n#if ', start)
block = text[start:end]
assert block.count('extern _Float16 ') == 13
output = root / 'state/sdk-overlay'
output.mkdir(parents=True, exist_ok=True)
header = output / 'math.h'
header.write_text(text[:start] + '#if defined(__FLT16_MANT_DIG__)\n' + block + '\n#endif\n' + text[end:])
overlay = {'version': 0, 'roots': [{'type': 'file', 'name': str(source), 'external-contents': str(header)}]}
(output / 'overlay.json').write_text(json.dumps(overlay, indent=2) + '\n')
(root / 'records/sdk-overlay.json').write_text(json.dumps({
    'sdk_header': str(source), 'sha256_original': hashlib.sha256(source.read_bytes()).hexdigest(),
    'sha256_overlay': hashlib.sha256(header.read_bytes()).hexdigest(),
    'change': 'Guard 13 macOS 15 _Float16 declarations with __FLT16_MANT_DIG__.'
}, indent=2) + '\n')
print(output / 'overlay.json')
