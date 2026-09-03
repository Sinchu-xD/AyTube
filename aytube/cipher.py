"""
Cipher extraction and deciphering for YouTube stream URLs.

Modern YouTube (2024+) uses AES-128-CTR encrypted signatures.
The key is NOT in player JS - it comes from onesie_hot_config.

Multi-strategy approach (executed in Node.js worker):
1. Base64 decode the signature (fast path)
2. Fetch onesie_hot_config from initplayback endpoint
3. Evaluate player JS in sandbox, intercept crypto.createCipheriv
4. Legacy: find numeric arrays / base64 strings in JS source

All strategies ultimately use AES-128-CTR with zero counter (symmetric).
"""

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile


def _node() -> str:
    """Find Node.js binary."""
    node = shutil.which('node')
    if not node:
        raise RuntimeError(
            'Node.js is required for modern cipher decryption. '
            'Install from https://nodejs.org/')
    return node


def _b64_decode(s: str) -> bytes | None:
    """Try URL-safe and standard base64 decode."""
    for variant in [s, s.replace('-', '+').replace('_', '/')]:
        try:
            padded = variant
            pad = 4 - len(variant) % 4
            if pad < 4:
                padded = variant + '=' * pad
            raw = base64.b64decode(padded)
            if len(raw) >= 8:
                return raw
        except Exception:
            continue
    return None


def _try_base64_sig(s: str) -> str | None:
    """Try to decode an 's' value as plain base64 signature."""
    raw = _b64_decode(s)
    if raw:
        try:
            text = raw.decode('utf-8', errors='strict')
            if all(c.isprintable() or c.isspace() for c in text):
                return text
        except UnicodeDecodeError:
            return raw.hex()
    return None


# ---------------------------------------------------------------------------
# Legacy Python cipher (ops-array based, older players)
# ---------------------------------------------------------------------------

def _parse_op(body: str):
    """Parse one cipher operation."""
    body = body.strip()
    if re.search(r'a\.reverse\s*\(\s*\)', body):
        return {'op': 'reverse'}
    m = re.search(r'a\.splice\s*\(\s*0\s*,\s*(\d+)\s*\)', body)
    if m:
        return {'op': 'splice', 'n': int(m.group(1))}
    m = re.search(r'a\.splice\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', body)
    if m:
        return {'op': 'slice', 'start': int(m.group(1)),
                'end': int(m.group(1)) + int(m.group(2))}
    m = re.search(r'a\s*=\s*a\.slice\s*\(\s*(\d+)\s*\)', body)
    if m:
        return {'op': 'slice', 'start': int(m.group(1)), 'end': None}
    m = re.search(
        r'var\s+\w+\s*=\s*a\[(\d+)\];\s*'
        r'a\[(\d+)\]\s*=\s*a\[(\d+)%?a\.length\];\s*'
        r'a\[(\d+)\]\s*=\s*\w+', body)
    if m:
        return {'op': 'swap', 'i': int(m.group(1)), 'j': int(m.group(4))}
    return None


def _extract_ops(js: str):
    """Extract cipher ops array from player JS. Returns (ops_list, var_name)."""
    arr_re = re.compile(
        r'var\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\[\s*'
        r'(?:function\s*\([^)]*\)\s*\{[^}]+\}[,\s]*){2,}'
        r'\]\s*;', re.DOTALL)

    m = arr_re.search(js)
    if not m:
        return None, None

    var_name = m.group(1)
    start = js.find(f'var {var_name} = [')
    if start < 0:
        return None, None

    bracket_start = js.index('[', start)
    depth = 0
    i = bracket_start
    while i < len(js):
        ch = js[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                break
        elif ch in ('"', "'"):
            q = ch
            i += 1
            while i < len(js) and js[i] != q:
                if js[i] == '\\':
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
        if op is not None:
            ops.append(op)

    return (ops if ops else None), var_name


def _build_python_cipher(ops: list, name=None):
    """Build a Python callable from ops list."""
    def cipher(sig: str) -> str:
        s = list(sig)
        for op in ops:
            if op['op'] == 'reverse':
                s.reverse()
            elif op['op'] == 'splice':
                n = min(op['n'], len(s))
                del s[:n]
            elif op['op'] == 'slice':
                end = op['end'] if op['end'] is not None else len(s)
                s = s[op['start']:end]
            elif op['op'] == 'swap':
                i, j = op['i'], op['j']
                j %= len(s)
                s[i], s[j] = s[j], s[i]
        return ''.join(s)
    cipher.__name__ = name or 'decipher'
    return cipher


# ---------------------------------------------------------------------------
# Node.js worker script (standalone file)
# ---------------------------------------------------------------------------

_WORKER_SCRIPT = """\
'use strict';
const crypto = require('crypto');
const https = require('https');
const http = require('http');
const fs = require('fs');

const jsCode = fs.readFileSync(process.argv[2], 'utf-8');
const sigValue = process.argv[3];
const cookiesFile = process.argv[4] || '';
const videoId = process.argv[5] || '';

function fetchURL(url, cookieHeader) {
    return new Promise((resolve, reject) => {
        const mod = url.startsWith('https') ? https : http;
        const headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        };
        if (cookieHeader) headers['Cookie'] = cookieHeader;
        const req = mod.get(url, { headers, timeout: 15000 }, (res) => {
            const chunks = [];
            res.on('data', d => chunks.push(d));
            res.on('end', () => {
                resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() });
            });
        });
        req.on('error', reject);
        req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    });
}

function loadCookies() {
    if (!cookiesFile || !fs.existsSync(cookiesFile)) return '';
    try {
        const lines = fs.readFileSync(cookiesFile, 'utf-8').split('\\n');
        const cookies = [];
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;
            const parts = trimmed.split('\\t');
            if (parts.length >= 7 && parts[5] && parts[6]) {
                cookies.push(parts[5] + '=' + parts[6]);
            }
        }
        return cookies.join('; ');
    } catch(e) { return ''; }
}

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
        if (text.length >= 8 && isPrintable(pt)) {
            return text;
        }
    } catch(e) {}
    return null;
}

function tryBase64Decode(sig) {
    try {
        let s2 = sig.replace(/\\s/g, '');
        while (s2.length % 4 !== 0) s2 += '=';
        s2 = s2.replace(/-/g, '+').replace(/_/g, '/');
        const decoded = Buffer.from(s2, 'base64');
        if (decoded.length >= 8 && isPrintable(decoded)) {
            return decoded.toString('utf-8');
        }
    } catch(e) {}
    return null;
}

function findNumericArrays(js) {
    const keys = [];
    const re = /var\\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\\s*=\\s*\\[\\s*([^\\]]{10,})\\]\\s*;?/g;
    let m;
    while ((m = re.exec(js)) !== null) {
        const nums = m[2].match(/-?\\d+/g);
        if (nums && nums.length === 16) {
            keys.push(Buffer.from(nums.map(n => parseInt(n) & 0xFF)));
        }
    }
    return keys;
}

function findB64Keys(js) {
    const keys = [];
    const re = /["']([A-Za-z0-9+/]{24,}={0,2})["']/g;
    const tried = new Set();
    let m;
    while ((m = re.exec(js)) !== null) {
        if (tried.has(m[1])) continue;
        tried.add(m[1]);
        const decoded = b64decode(m[1]);
        if (decoded && decoded.length === 16) {
            keys.push(decoded);
        }
    }
    return keys;
}

async function fetchOnesieHotConfig() {
    const cookieHeader = loadCookies();
    const hosts = ['www.youtube.com', 'm.youtube.com'];
    for (const host of hosts) {
        const url = 'https://' + host + '/initplayback?owc=1';
        try {
            const resp = await fetchURL(url, cookieHeader);
            if (resp.status === 200 && resp.body.includes('clientKey')) {
                console.error('[worker] Got onesie from ' + host);
                return resp.body;
            }
            console.error('[worker] ' + host + ' HTTP ' + resp.status);
        } catch(e) {
            console.error('[worker] Error: ' + e.message);
        }
    }
    return null;
}

(async function main() {
    const enc = b64decode(sigValue.replace(/\\s/g, ''));

    // Step 1: Base64 decode
    console.error('[worker] Step 1: Base64 decode...');
    const r1 = tryBase64Decode(sigValue);
    if (r1) { console.log(r1); process.exit(0); }

    // Step 2: Use predefined key if available (from HTML extraction)
    if (typeof PREDEFINED_KEY_B64 !== 'undefined' && PREDEFINED_KEY_B64) {
        console.error('[worker] Step 2a: Using predefined key...');
        const key = b64decode(PREDEFINED_KEY_B64);
        if (key && key.length === 16 && enc) {
            const r = aes128ctrDecrypt(enc, key);
            if (r) { console.log(r); process.exit(0); }
        }
    }

    // Step 2: onesie_hot_config
    console.error('[worker] Step 2: Fetch onesie_hot_config...');
    const onesie = await fetchOnesieHotConfig();
    if (onesie) {
        try {
            const config = JSON.parse(onesie);
            const keyB64 = config.clientKey || config.CLIENT_KEY;
            if (keyB64) {
                const key = b64decode(keyB64);
                if (key && key.length === 16 && enc) {
                    const r = aes128ctrDecrypt(enc, key);
                    if (r) { console.log(r); process.exit(0); }
                }
            }
        } catch(e) { console.error('[worker] Parse error:', e.message); }
    }

    // Step 3: JS eval with key capture
    console.error('[worker] Step 3: JS eval with key capture...');
    try {
        const script = buildEvalScript();
        const tmp = '/tmp/yt_eval_' + Date.now() + '.js';
        fs.writeFileSync(tmp, script);
        const execSync = require('child_process').execSync;
        const stdout = execSync('node ' + tmp, { encoding: 'utf-8', timeout: 45000 });
        try { fs.unlinkSync(tmp); } catch(e) {}

        const keyMatch = stdout.match(/===KEYS===\\n([\\s\\S]*?)===END===/);
        if (keyMatch) {
            const keyLines = keyMatch[1].trim().split('\\n').filter(l => l.trim());
            console.error('[worker] Captured keys:', keyLines.length);
            if (enc) {
                for (const kh of keyLines) {
                    const key = Buffer.from(kh, 'hex');
                    if (key.length === 16) {
                        const r = aes128ctrDecrypt(enc, key);
                        if (r) { console.log(r); process.exit(0); }
                    }
                }
            }
        }
    } catch(e) {
        console.error('[worker] Eval failed:', e.message);
    }

    // Step 4: Legacy key search
    console.error('[worker] Step 4: Searching JS source...');
    const numKeys = findNumericArrays(jsCode);
    const b64Keys = findB64Keys(jsCode);
    const allKeys = numKeys.concat(b64Keys);
    console.error('[worker] Found', allKeys.length, 'candidate keys');
    if (enc) {
        for (const key of allKeys) {
            const r = aes128ctrDecrypt(enc, key);
            if (r) { console.log(r); process.exit(0); }
        }
    }

    console.error('[worker] All strategies failed');
    process.exit(1);

    function buildEvalScript() {
        return "'use strict';\\n" +
            "const crypto = require('crypto');\\n" +
            "const capturedKeys = [];\\n" +
            "let fetchCount = 0;\\n" +
            "const g = {};\\n" +
            "g.TextEncoder = TextEncoder; g.Uint8Array = Uint8Array; g.DataView = DataView;\\n" +
            "g.ArrayBuffer = ArrayBuffer; g.Float32Array = Float32Array; g.Float64Array = Float64Array;\\n" +
            "g.Int8Array = Int8Array; g.Int16Array = Int16Array; g.Int32Array = Int32Array;\\n" +
            "g.Uint16Array = Uint16Array; g.Uint32Array = Uint32Array;\\n" +
            "g.Map = Map; g.Set = Set; g.WeakMap = WeakMap; g.WeakSet = WeakSet;\\n" +
            "g.Symbol = Symbol; g.Promise = Promise; g.JSON = JSON; g.RegExp = RegExp;\\n" +
            "g.Error = Error; g.TypeError = TypeError; g.RangeError = RangeError;\\n" +
            "g.Math = Math; g.Date = Date; g.Number = Number; g.String = String; g.Boolean = Boolean;\\n" +
            "g.Object = Object; g.Array = Array; g.Function = Function;\\n" +
            "g.URL = URL; g.URLSearchParams = URLSearchParams;\\n" +
            "g.console = { log:()=>{}, warn:()=>{}, error:()=>{}, debug:()=>{}, trace:()=>{} };\\n" +
            "g.isNaN = isNaN; g.parseFloat = parseFloat; g.parseInt = parseInt;\\n" +
            "g.WebAssembly = undefined;\\n" +
            "g.sessionStorage = { getItem:()=>null, setItem:()=>{}, removeItem:()=>{}, length:0, key:()=>null };\\n" +
            "g.localStorage = { getItem:()=>null, setItem:()=>{}, removeItem:()=>{}, length:0, key:()=>null };\\n" +
            "g.navigator = { userAgent:'Mozilla/5.0', language:'en', languages:['en'] };\\n" +
            "g.document = { location:{ toString:()=>'https://www.youtube.com', href:'https://www.youtube.com', hostname:'www.youtube.com' }, addEventListener:()=>{}, createElement:()=>({}) };\\n" +
            "g.performance = { now:()=>Date.now(), timeOrigin:Date.now(), timing:{navigationStart:Date.now()} };\\n" +
            "g.window = g;\\n" +
            "g.setTimeout = () => {}; g.clearTimeout = () => {};\\n" +
            "g.setInterval = () => {}; g.clearInterval = () => {};\\n" +
            "g.Buffer = Buffer;\\n" +
            "g.URL.createObjectURL = () => 'blob:test';\\n" +
            "g.crypto = { getRandomValues(a) {\\n" +
            "    const v = new Uint8Array(a.byteLength || a.length);\\n" +
            "    for(let i=0;i<v.length;i++) v[i]=Math.floor(Math.random()*256);\\n" +
            "    a.set ? a.set(v) : (()=>{for(let j=0;j<v.length;j++) a[j]=v[j];})();\\n" +
            "    return a;\\n" +
            "}};\\n" +
            "g.fetch = async function(url, opts) { fetchCount++; return {\\n" +
            "    status: 200, ok: true, text: async () => '{}', json: async () => ({}),\\n" +
            "    arrayBuffer: async () => Buffer.alloc(0), headers: new Map(), clone: function() { return this; } }; };\\n" +
            "g.XMLHttpRequest = function() { return { open:()=>{}, send:()=>{}, setRequestHeader:()=>{}, status:200, readyState:4, responseText:'{}' }; };\\n" +
            "g.Worker = function() {};\\n" +
            "const origCipheriv = crypto.createCipheriv;\\n" +
            "crypto.createCipheriv = function(alg, key, iv) {\\n" +
            "    if (alg && alg.includes('aes-128-ctr') && key) {\\n" +
            "        const len = key.length || key.byteLength || 0;\\n" +
            "        if (len === 16) capturedKeys.push(Buffer.from(key).toString('hex'));\\n" +
            "    }\\n" +
            "    return origCipheriv.apply(this, arguments);\\n" +
            "};\\n" +
            "console.error('[eval] Evaluating player JS...');\\n" +
            "try { eval(" + JSON.stringify(jsCode) + "); } catch(e) {}\\n" +
            "console.error('[eval] Done. Keys:', capturedKeys.length);\\n" +
            "console.log('===KEYS==='); capturedKeys.forEach(k => console.log(k));\\n" +
            "console.log('===END===');
    }
})().catch(e => { console.error('[worker] Fatal:', e.message); process.exit(1); });
"""


# ---------------------------------------------------------------------------
# Node.js worker execution
# ---------------------------------------------------------------------------

def _run_node_worker(js_code: str, sig: str, cookies_file=None,
                     video_id=None, aes_key=None) -> str | None:
    """
    Run the Node.js worker to decrypt a signature.

    Returns the deciphered string or None on failure.

    If aes_key (16 bytes) is provided, the worker will use it directly
    for AES-128-CTR decryption, skipping the key search phase.
    """
    try:
        node = _node()
    except RuntimeError:
        return None

    js_tmp = None
    worker_tmp = None
    try:
        fd, js_tmp = tempfile.mkstemp(suffix='.js', prefix='yt_js_')
        with os.fdopen(fd, 'w') as f:
            f.write(js_code)

        # Write worker with optional key
        key_b64 = base64.b64encode(aes_key).decode() if aes_key else ''
        worker_code = _WORKER_SCRIPT
        if key_b64:
            # Prepend the key to the worker so it can use it directly
            worker_code = f"const PREDEFINED_KEY_B64 = '{key_b64}';\n" + worker_code

        fd2, worker_tmp = tempfile.mkstemp(suffix='.js', prefix='yt_worker_')
        with os.fdopen(fd2, 'w') as f:
            f.write(worker_code)

        proc = subprocess.run(
            [node, worker_tmp, js_tmp, sig, cookies_file or '',
             video_id or ''],
            capture_output=True, text=True, timeout=90,
        )

        if proc.returncode != 0:
            return None

        output = proc.stdout.strip()
        for line in reversed(output.split('\n')):
            line = line.strip()
            if not line:
                continue
            if line.startswith('===') or line.startswith('[worker'):
                continue
            if len(line) >= 8:
                return line

        return None
    except Exception:
        return None
    finally:
        for tmp in [js_tmp, worker_tmp]:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# n-parameter transformation
# ---------------------------------------------------------------------------

def _extract_n_function(js: str):
    """Find the n-parameter transformation function in player JS."""
    ops, var_name = _extract_ops(js)
    if not ops:
        return None
    return _build_python_cipher(ops, 'n_transform')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_key(js: str, html: str | None = None) -> bytes | None:
    """
    Try to extract the AES cipher key from player JS and/or page HTML.

    Strategy 1: onesie_hot_config from HTML page config
      - The HTML page contains a ytInitialPlayerResponse JSON with
        webPlayerContextConfig.onesieHotConfig or similar
      - Or the page has a separate config object with onesie_hot_config
      - The clientKey field (base64) is the 16-byte AES key

    Strategy 2: onesie_hot_config from initplayback endpoint
      - The player JS references /initplayback?owc=1
      - Fetch that endpoint to get clientKey

    Returns 16-byte AES key or None.
    """
    # Strategy 1: HTML extraction
    if html:
        key = _extract_key_from_html(html)
        if key:
            return key

    # Strategy 2: initplayback endpoint (via Node.js worker)
    if js:
        key = _extract_key_from_initplayback(js)
        if key:
            return key

    return None


def _extract_key_from_html(html: str) -> bytes | None:
    """
    Extract onesie_hot_config.clientKey from the HTML page.

    The blo constructor in player JS reads D.onesie_hot_config where D is
    the page config object. We need to find this config in the HTML.
    """
    if not html:
        return None

    # Pattern 1: Look for onesie_hot_config as a JSON field in the page
    # It can appear in various forms in the HTML
    patterns = [
        # Direct onesie_hot_config with clientKey
        r'"onesie_hot_config"\s*:\s*\{[^}]*"clientKey"\s*:\s*"([^"]+)"',
        r'"onesieHotConfig"\s*:\s*\{[^}]*"clientKey"\s*:\s*"([^"]+)"',
        # onesie_hot_config as a separate JSON blob
        r'"onesie_hot_config"\s*:\s*"([^"]+)"',
        r'"onesieHotConfig"\s*:\s*"([^"]+)"',
        # In webPlayerContextConfig
        r'"webPlayerContextConfig"\s*:\s*\{[^}]*"onesieHotConfig"\s*:\s*\{[^}]*"clientKey"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            key_str = m.group(1)
            key_raw = _b64_decode(key_str)
            if key_raw and len(key_raw) == 16:
                return key_raw

    # Pattern 2: Look for clientKey anywhere in the HTML (broad search)
    m = re.search(r'"clientKey"\s*:\s*"([A-Za-z0-9+/=]+)"', html)
    if m:
        key_raw = _b64_decode(m.group(1))
        if key_raw and len(key_raw) == 16:
            return key_raw

    # Pattern 3: Look for ytInitialPlayerResponse with embedded config
    m = re.search(r'ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*</script>',
                  html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            # Check streamingData for any config
            streaming_data = data.get('streamingData', {})
            # Check videoDetails
            video_details = data.get('videoDetails', {})
            # Check for webPlayerContextConfig in response
            ctx = data.get('webPlayerContextConfig', {})
            onesie = ctx.get('onesieHotConfig', ctx.get('onesie_hot_config'))
            if onesie:
                key_str = onesie.get('clientKey', onesie.get('CLIENT_KEY', ''))
                if key_str:
                    key_raw = _b64_decode(key_str)
                    if key_raw and len(key_raw) == 16:
                        return key_raw
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return None


def _extract_key_from_initplayback(js: str) -> bytes | None:
    """
    Extract the AES key by fetching onesie_hot_config from initplayback.

    Extracts the initplayback URL pattern from player JS and tries
    to fetch the config.
    """
    if not js:
        return None

    # Find initplayback URL patterns
    urls = re.findall(r'https?://[^\s"\']*initplayback[^\s"\']*', js)
    if not urls:
        return None

    # Try each URL with owc=1 parameter
    for base_url in urls[:5]:
        try:
            url = base_url if 'owc=1' in base_url else base_url + '&owc=1'
            if '?' not in url:
                url = base_url + '?owc=1'

            import urllib.request
            req = urllib.request.Request(url, headers={
                'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/138.0.0.0 Safari/537.36'),
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode('utf-8', errors='replace')

            if 'clientKey' in body:
                config = json.loads(body)
                key_str = config.get('clientKey', config.get('CLIENT_KEY', ''))
                if key_str:
                    key_raw = _b64_decode(key_str)
                    if key_raw and len(key_raw) == 16:
                        return key_raw
        except Exception:
            continue

    return None


def extract_cipher_function(js: str, aes_key: bytes | None = None):
    """
    Extract the signature decipher function from player JS.

    Parameters
    ----------
    js : str
        Player JavaScript source code.
    aes_key : bytes | None
        16-byte AES key. If provided, the Node.js worker will use it
        directly without trying to search for it.

    Returns a callable, or None on failure.

    Tries strategies in order:
    1. Legacy ops-array (Python)
    2. Node.js worker (modern AES-128-CTR)
    """
    # Strategy 1: Legacy ops array
    ops, var_name = _extract_ops(js)
    if ops:
        return _build_python_cipher(ops, var_name)

    # Strategy 2: Node.js worker (handles modern AES-128-CTR)
    try:
        return _NodeCipher(js, aes_key=aes_key)
    except RuntimeError:
        return None


class _NodeCipher:
    """Cipher that uses Node.js to decipher modern signatures."""

    def __init__(self, js_code: str, aes_key: bytes | None = None):
        self._js = js_code
        self._key = aes_key
        self._node = _node()

    def __call__(self, sig: str) -> str:
        result = _try_base64_sig(sig)
        if result:
            return result

        result = _run_node_worker(self._js, sig, aes_key=self._key)
        if result:
            return result

        raise RuntimeError(
            'Could not decipher signature. YouTube may have updated their '
            'obfuscation scheme beyond what this tool supports. '
            'Try providing a cookies_file file with an authenticated session.')


def extract_n_function(js: str):
    """Extract the n-parameter transformation function."""
    return _extract_n_function(js)


def decipher(cipher_func, signature: str) -> str:
    """Apply the cipher function to a signature string."""
    return cipher_func(signature)


def decipher_n(n_func, n_value: str) -> str:
    """Apply the n-parameter transformation function."""
    if n_func:
        return n_func(n_value)
    return n_value
