"""
aytube.cipher - Reverse-engineered signature and n-parameter deciphering.

Handles YouTube's signature scrambling (legacy array operations and modern AES-128-CTR)
and n-parameter throttling deciphering.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from typing import Any, Callable

# ── Cipher URL Helpers ────────────────────────────────────────────────────────

def decode_signature_cipher(cipher_str: str) -> dict[str, str]:
    """
    Parse a YouTube signatureCipher query string.
    Note: Must NOT unquote before parse_qs to avoid splitting embedded & within url.
    """
    params = urllib.parse.parse_qs(cipher_str)
    return {k: (params[k][0] if params.get(k) else "") for k in ("s", "sp", "url", "n")}


def resolve_signature_format(fmt: dict) -> str:
    """Extract full stream URL from format dictionary."""
    if fmt.get("signatureCipher"):
        parts = decode_signature_cipher(fmt["signatureCipher"])
        base_url = parts.get("url", "")
        sp = parts.get("sp", "signature")
        sig = parts.get("s", "")
        if base_url and sig:
            sep = "&" if "?" in base_url else "?"
            return f"{base_url}{sep}{sp}={sig}"
        return base_url

    if fmt.get("url"):
        url_str = fmt["url"]
        sig = fmt.get("s", "")
        sp = fmt.get("sp", "signature")
        if sig:
            sep = "&" if "?" in url_str else "?"
            url_str = f"{url_str}{sep}{sp}={sig}"
        return url_str

    return ""


def has_cipher(all_formats: list[dict]) -> bool:
    """Check if any format contains encrypted signature parameters."""
    return any(fmt.get("signatureCipher") or fmt.get("s") for fmt in all_formats)


def has_n_parameter(all_formats: list[dict]) -> bool:
    """Check if formats require n-parameter anti-throttling deciphering."""
    for fmt in all_formats:
        cipher = fmt.get("signatureCipher", "")
        if "&n=" in cipher or fmt.get("n"):
            return True
    return False


def apply_n_parameter(url: str, n_value: str, n_func: Callable | None) -> str:
    """Transform and update the n-parameter in the stream URL to avoid download throttling."""
    if not n_value or not n_func:
        return url
    try:
        new_n = decipher_n(n_func, n_value)
        if new_n and new_n != n_value:
            if "&n=" in url:
                url = re.sub(r'([?&])n=[^&]+', rf'\g<1>n={new_n}', url)
            else:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}n={new_n}"
    except Exception:
        pass
    return url


# ── Signature Deciphering Strategies ──────────────────────────────────────────

def _node_binary() -> str | None:
    return shutil.which("node")


def _b64_decode(s: str) -> bytes | None:
    for variant in [s, s.replace("-", "+").replace("_", "/")]:
        try:
            pad = 4 - len(variant) % 4
            if pad < 4:
                variant = variant + "=" * pad
            raw = base64.b64decode(variant)
            if len(raw) >= 8:
                return raw
        except Exception:
            continue
    return None


def _try_base64_sig(s: str) -> str | None:
    raw = _b64_decode(s)
    if raw:
        try:
            text = raw.decode("utf-8", errors="strict")
            if all(c.isprintable() or c.isspace() for c in text):
                return text
        except UnicodeDecodeError:
            pass
    return None


def _parse_op(body: str) -> dict[str, Any] | None:
    body = body.strip()
    if re.search(r'a\.reverse\s*\(\s*\)', body):
        return {"op": "reverse"}
    m = re.search(r'a\.splice\s*\(\s*0\s*,\s*(\d+)\s*\)', body)
    if m:
        return {"op": "splice", "n": int(m.group(1))}
    m = re.search(r'a\.splice\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', body)
    if m:
        return {"op": "slice", "start": int(m.group(1)), "end": int(m.group(1)) + int(m.group(2))}
    m = re.search(r'a\s*=\s*a\.slice\s*\(\s*(\d+)\s*\)', body)
    if m:
        return {"op": "slice", "start": int(m.group(1)), "end": None}
    m = re.search(
        r'var\s+\w+\s*=\s*a\[(\d+)\];\s*'
        r'a\[(\d+)\]\s*=\s*a\[(\d+)%?a\.length\];\s*'
        r'a\[(\d+)\]\s*=\s*\w+', body
    )
    if m:
        return {"op": "swap", "i": int(m.group(1)), "j": int(m.group(4))}
    return None


def _extract_ops(js: str) -> tuple[list[dict] | None, str | None]:
    arr_re = re.compile(
        r'var\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\[\s*'
        r'(?:function\s*\([^)]*\)\s*\{[^}]+\}[,\s]*){2,}'
        r'\]\s*;', re.DOTALL
    )
    m = arr_re.search(js)
    if not m:
        return None, None

    var_name = m.group(1)
    start = js.find(f"var {var_name} = [")
    if start < 0:
        return None, None

    bracket_start = js.index("[", start)
    depth = 0
    i = bracket_start
    while i < len(js):
        ch = js[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        elif ch in ('"', "'"):
            q = ch
            i += 1
            while i < len(js) and js[i] != q:
                if js[i] == "\\":
                    i += 1
                i += 1
        i += 1

    if depth != 0:
        return None, None

    arr_str = js[bracket_start:i + 1]
    func_re = re.compile(r'function\s*\([^)]*\)\s*\{([^}]+)\}')
    bodies = func_re.findall(arr_str)

    ops = []
    for body in bodies:
        op = _parse_op(body.strip())
        if op:
            ops.append(op)

    return (ops if ops else None), var_name


def _build_python_cipher(ops: list[dict], name: str = "decipher") -> Callable:
    def cipher(sig: str) -> str:
        s = list(sig)
        for op in ops:
            if op["op"] == "reverse":
                s.reverse()
            elif op["op"] == "splice":
                n = min(op["n"], len(s))
                del s[:n]
            elif op["op"] == "slice":
                end = op["end"] if op["end"] is not None else len(s)
                s = s[op["start"]:end]
            elif op["op"] == "swap":
                i, j = op["i"], op["j"]
                j %= len(s)
                s[i], s[j] = s[j], s[i]
        return "".join(s)

    cipher.__name__ = name
    return cipher


_NODE_WORKER_SCRIPT = """\
'use strict';
const crypto = require('crypto');
const https = require('https');
const http = require('http');
const fs = require('fs');

const jsCode = fs.readFileSync(process.argv[2], 'utf-8');
const sigValue = process.argv[3];
const cookiesFile = process.argv[4] || '';

function b64decode(s) {
    try {
        let s2 = s.replace(/-/g, '+').replace(/_/g, '/');
        const pad = 4 - (s2.length % 4);
        if (pad < 4) s2 += '='.repeat(pad);
        return Buffer.from(s2, 'base64');
    } catch(e) { return null; }
}

function isPrintable(buf) {
    if (buf.length < 8) return false;
    for (let i = 0; i < buf.length; i++) {
        const c = buf[i];
        if ((c >= 32 && c <= 126) || c === 0 || c === 10 || c === 13) continue;
        return false;
    }
    return true;
}

function aes128ctrDecrypt(encrypted, key) {
    try {
        const counter = Buffer.alloc(16, 0);
        const d = crypto.createDecipheriv('aes-128-ctr', key, counter);
        d.setAutoPadding(false);
        const pt = Buffer.concat([d.update(encrypted), d.final()]);
        const text = pt.toString('utf-8');
        if (text.length >= 8 && isPrintable(pt)) return text;
    } catch(e) {}
    return null;
}

function tryBase64(sig) {
    try {
        let s2 = sig.replace(/\\s/g, '');
        while (s2.length % 4 !== 0) s2 += '=';
        s2 = s2.replace(/-/g, '+').replace(/_/g, '/');
        const decoded = Buffer.from(s2, 'base64');
        if (decoded.length >= 8 && isPrintable(decoded)) return decoded.toString('utf-8');
    } catch(e) {}
    return null;
}

(function main() {
    const enc = b64decode(sigValue.replace(/\\s/g, ''));
    const r1 = tryBase64(sigValue);
    if (r1) { console.log(r1); process.exit(0); }

    if (typeof PREDEFINED_KEY_B64 !== 'undefined' && PREDEFINED_KEY_B64) {
        const key = b64decode(PREDEFINED_KEY_B64);
        if (key && key.length === 16 && enc) {
            const r = aes128ctrDecrypt(enc, key);
            if (r) { console.log(r); process.exit(0); }
        }
    }
    process.exit(1);
})();
"""


class _NodeCipher:
    """Node.js cryptographic engine wrapper."""
    def __init__(self, js_code: str, aes_key: bytes | None = None):
        self._js = js_code
        self._key = aes_key
        self._node = _node_binary()
        if not self._node:
            raise RuntimeError("Node.js is not available on system.")

    def __call__(self, sig: str) -> str:
        b64_res = _try_base64_sig(sig)
        if b64_res:
            return b64_res

        js_tmp = None
        worker_tmp = None
        try:
            fd, js_tmp = tempfile.mkstemp(suffix=".js", prefix="yt_js_")
            with os.fdopen(fd, "w") as f:
                f.write(self._js)

            worker_code = _NODE_WORKER_SCRIPT
            if self._key:
                k_b64 = base64.b64encode(self._key).decode()
                worker_code = f"const PREDEFINED_KEY_B64 = '{k_b64}';\n" + worker_code

            fd2, worker_tmp = tempfile.mkstemp(suffix=".js", prefix="yt_worker_")
            with os.fdopen(fd2, "w") as f:
                f.write(worker_code)

            proc = subprocess.run(
                [self._node, worker_tmp, js_tmp, sig],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                res = proc.stdout.strip()
                if len(res) >= 8:
                    return res
        except Exception:
            pass
        finally:
            for p in (js_tmp, worker_tmp):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

        raise RuntimeError("Could not decipher signature with current player cipher.")


def extract_key(js: str = "", html: str | None = None) -> bytes | None:
    """Extract onesie_hot_config 16-byte AES clientKey from HTML."""
    if not html:
        return None
    patterns = [
        r'"onesie_hot_config"\s*:\s*\{[^}]*"clientKey"\s*:\s*"([^"]+)"',
        r'"onesieHotConfig"\s*:\s*\{[^}]*"clientKey"\s*:\s*"([^"]+)"',
        r'"clientKey"\s*:\s*"([A-Za-z0-9+/=]+)"',
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            raw = _b64_decode(m.group(1))
            if raw and len(raw) == 16:
                return raw
    return None


def extract_cipher_function(js: str, aes_key: bytes | None = None) -> Callable | None:
    """Extract callable decipher function from player JavaScript."""
    ops, var_name = _extract_ops(js)
    if ops:
        return _build_python_cipher(ops, var_name or "decipher")

    if _node_binary():
        try:
            return _NodeCipher(js, aes_key=aes_key)
        except Exception:
            pass
    return None


def extract_n_function(js: str) -> Callable | None:
    """Extract n-parameter transformation function."""
    ops, _ = _extract_ops(js)
    if ops:
        return _build_python_cipher(ops, "n_transform")
    return None


def decipher(cipher_func: Callable, signature: str) -> str:
    """Execute cipher function on signature."""
    return cipher_func(signature)


def decipher_n(n_func: Callable | None, n_value: str) -> str:
    """Execute n-parameter deciphering on token."""
    if n_func:
        return n_func(n_value)
    return n_value
