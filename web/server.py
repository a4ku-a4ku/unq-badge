#!/usr/bin/env python3
"""
Discord 7K Badge Farmer - Multi-Account Web Server (12 Slots)
Fixed automated 7,000 games spoofing with zero manual configuration.
Only requires:
  1. Discord Account Token
  2. Cloudflare cf_clearance Cookie
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import queue
import secrets
import string
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Generator, Sequence, Optional, Dict, Any

from flask import Flask, jsonify, request, render_template, Response, stream_with_context

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
CANDIDATE_GAMES_FILES = [
    ROOT / "games.json",
    PROJECT_ROOT / "games.json",
    PROJECT_ROOT.parent / "data" / "games.json",
]

ME_URL = "https://discord.com/api/v9/users/@me?with_analytics_token=true"
SCIENCE_URL = "https://discord.com/api/v9/science"
PROPERTIES_URL = "https://cordapi.dolfi.es/api/v2/properties/windows"
GAMES_CDN_URL = "https://cdn.discordapp.com/detectables/games.json"

TARGET_GAMES_COUNT = 7000
BATCH_SIZE = 50
BATCH_DELAY = 0.30
MAX_SLOTS = 12

CLIENT_VERSION = "1.0.9253"
CLIENT_BUILD_NUMBER = 594031
NATIVE_BUILD_NUMBER = 88414
OS_VERSION = "10.0.26200"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) discord/1.0.9253 Chrome/148.0.7778.280 "
    "Electron/42.7.1 Safari/537.36"
)

# PowerShell script for generating native Windows executable fingerprint
_FINGERPRINT_PS1 = r'''
param(
  [int]$ProcessId = 0,
  [string]$Path,
  [Parameter(Mandatory = $true)][string]$UserId
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class CertPubKeyHash {
  const uint X509_ASN_ENCODING = 0x00000001;
  const uint PKCS_7_ASN_ENCODING = 0x00010000;
  const uint CALG_SHA_256 = 0x0000800C;

  [StructLayout(LayoutKind.Sequential)] struct Blob { public uint cbData; public IntPtr pbData; }
  [StructLayout(LayoutKind.Sequential)] struct AlgId { public IntPtr pszObjId; public Blob Parameters; }
  [StructLayout(LayoutKind.Sequential)] struct BitBlob { public uint cbData; public IntPtr pbData; public uint cUnusedBits; }
  [StructLayout(LayoutKind.Sequential)] struct PubKeyInfo { public AlgId Algorithm; public BitBlob PublicKey; }
  [StructLayout(LayoutKind.Sequential)] struct FileTime { public uint Low; public uint High; }
  [StructLayout(LayoutKind.Sequential)]
  struct CertInfo {
    public uint Version; public Blob SerialNumber; public AlgId SignatureAlgorithm; public Blob Issuer;
    public FileTime NotBefore; public FileTime NotAfter; public Blob Subject;
    public PubKeyInfo SubjectPublicKeyInfo; public BitBlob IssuerUniqueId; public BitBlob SubjectUniqueId;
    public uint ExtensionCount; public IntPtr Extensions;
  }
  [StructLayout(LayoutKind.Sequential)]
  struct CertContext {
    public uint EncodingType; public IntPtr Encoded; public uint EncodedSize;
    public IntPtr CertInfo; public IntPtr Store;
  }

  [DllImport("crypt32.dll", SetLastError = true)]
  static extern bool CryptHashPublicKeyInfo(
    IntPtr provider, uint algid, uint flags, uint encoding, ref PubKeyInfo info, byte[] hash, ref uint hashSize);

  public static byte[] Hash(IntPtr certContext) {
    var ctx = Marshal.PtrToStructure<CertContext>(certContext);
    var info = Marshal.PtrToStructure<CertInfo>(ctx.CertInfo);
    var hash = new byte[32];
    uint hashSize = 32;
    if (!CryptHashPublicKeyInfo(IntPtr.Zero, CALG_SHA_256, 0, X509_ASN_ENCODING | PKCS_7_ASN_ENCODING, ref info.SubjectPublicKeyInfo, hash, ref hashSize) || hashSize != 32)
      throw new InvalidOperationException("CryptHashPublicKeyInfo failed");
    return hash;
  }
}
"@

if (!$Path) {
  if (!$ProcessId) { throw "Pass -Path <exe> or -ProcessId <pid>." }
  $Path = (Get-Process -Id $ProcessId).Path
}
if (!$Path) { throw "Could not resolve executable path." }

$fs = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
try {
  $fileSize = [UInt64]$fs.Length
  $readSize = [int][Math]::Min($fs.Length, 0x10000)
  $buf = [byte[]]::new($readSize)
  $read = $fs.Read($buf, 0, $readSize)
  if ($read -lt 0x40) { throw "File prefix is too small." }
  if ($read -ne $readSize) { [Array]::Resize([ref]$buf, $read) }
} finally {
  $fs.Dispose()
}

if ([BitConverter]::ToUInt16($buf, 0) -ne 0x5A4D) { throw "Not an MZ executable." }
$pe = [BitConverter]::ToInt32($buf, 0x3C)
if ($pe -lt 0 -or [BitConverter]::ToUInt32($buf, $pe) -ne 0x4550) { throw "Not a PE executable." }

$fh = $pe + 4
$sections = [BitConverter]::ToUInt16($buf, $fh + 2)
$timestamp = [BitConverter]::ToUInt32($buf, $fh + 4)
$optSize = [BitConverter]::ToUInt16($buf, $fh + 16)
$opt = $fh + 20
$isPe32Plus = [BitConverter]::ToUInt16($buf, $opt) -eq 0x20B
if (!$isPe32Plus) { throw "Discord only fingerprints PE32+." }
$sizeOfImage = [BitConverter]::ToUInt32($buf, $opt + 56)

$sectionTable = $opt + $optSize
$sha256 = [Security.Cryptography.SHA256]::Create()
$headerHash = $sha256.ComputeHash([byte[]]$buf[0..($sectionTable - 1)])
$sectionHash = $sha256.ComputeHash([byte[]]$buf[$sectionTable..($sectionTable + $sections * 40 - 1)])

$machineGuid = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Cryptography" -Name MachineGuid).MachineGuid
$machineUserHash = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($machineGuid + $UserId))

$sig = Get-AuthenticodeSignature -LiteralPath $Path
$signed = $sig.Status -eq "Valid" -and $sig.SignerCertificate
if ($signed) {
  $name = $sig.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
  $certHash = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($name) + [CertPubKeyHash]::Hash($sig.SignerCertificate.Handle))
} else {
  $certHash = [byte[]]::new(32)
}

$flags = 0
if ($signed) { $flags += 1 }
if ($isPe32Plus) { $flags += 2 }

$out = [byte[]](@(1, [byte]$flags) +
  [BitConverter]::GetBytes($fileSize) +
  [BitConverter]::GetBytes($timestamp) +
  [BitConverter]::GetBytes($sizeOfImage) +
  $headerHash + $machineUserHash + $sectionHash + $certHash)

$key = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($UserId + "https://discord.com/careers"))
for ($i = 1; $i -lt $out.Length; $i++) {
  $out[$i] = $out[$i] -bxor $key[($i - 1) -band 31]
}

[Convert]::ToBase64String($out)
'''


def user_id_from_token(token: str) -> str:
    try:
        first = token.split(".", 1)[0]
        pad = "=" * (-len(first) % 4)
        return base64.b64decode(first + pad).decode("utf-8")
    except Exception:
        return ""


def generate_fingerprint_safe(user_id: str) -> str:
    if os.name != "nt" or not user_id:
        return ""
    import glob
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
        r"C:\Windows\System32\notepad.exe",
        r"C:\Windows\explorer.exe"
    ]
    exe_path = ""
    for cand in candidates:
        matches = glob.glob(cand)
        if matches and Path(matches[0]).exists():
            exe_path = matches[0]
            break

    if not exe_path:
        return ""

    script = Path(tempfile.gettempdir()) / f"disc_fp_{uuid.uuid4().hex}.ps1"
    try:
        script.write_text(_FINGERPRINT_PS1, encoding="utf-8")
        args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script), "-UserId", user_id, "-Path", exe_path]
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            out = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if out:
                return out[-1]
    except Exception:
        pass
    finally:
        try:
            script.unlink()
        except OSError:
            pass
    return ""


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    exe: str


def _win_exe(game: dict) -> str:
    for entry in game.get("executables", []):
        if entry.get("os") == "win32" and entry.get("name"):
            return entry["name"]
    return "game.exe"


def load_games_catalog() -> list[Game]:
    raw = ""
    for candidate in CANDIDATE_GAMES_FILES:
        if candidate.exists():
            try:
                raw = candidate.read_text(encoding="utf-8").strip()
                if raw:
                    break
            except Exception:
                pass
    if not raw:
        try:
            req = urllib.request.Request(GAMES_CDN_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            try:
                save_target = CANDIDATE_GAMES_FILES[0]
                save_target.parent.mkdir(parents=True, exist_ok=True)
                save_target.write_text(raw, encoding="utf-8")
            except Exception:
                pass
        except Exception:
            return []

    try:
        data = json.loads(raw)
        games: list[Game] = []
        seen = set()
        for entry in data:
            gid = str(entry.get("id", ""))
            if not gid.isdigit() or gid in seen:
                continue
            if not any(e.get("os") == "win32" and e.get("name") for e in entry.get("executables", [])):
                continue
            seen.add(gid)
            games.append(Game(gid, entry.get("name", "Unknown"), _win_exe(entry)))
        return games
    except Exception:
        return []


GLOBAL_GAMES: list[Game] = []


def _ensure_games_loaded():
    global GLOBAL_GAMES
    if not GLOBAL_GAMES:
        loaded = load_games_catalog()
        if loaded:
            GLOBAL_GAMES = loaded


# Eager background preload on import (ensures games ready immediately under Gunicorn/Render)
threading.Thread(target=_ensure_games_loaded, daemon=True).start()



def _local_props() -> dict:
    return {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": CLIENT_VERSION,
        "os_version": OS_VERSION,
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "en-US",
        "has_client_mods": False,
        "browser_user_agent": USER_AGENT,
        "browser_version": "42.7.1",
        "os_sdk_version": "26200",
        "client_build_number": CLIENT_BUILD_NUMBER,
        "native_build_number": NATIVE_BUILD_NUMBER,
        "client_event_source": None,
        "client_app_state": "focused",
    }


def build_super_props(launch_signature: str, heartbeat_session: str) -> str:
    try:
        req = urllib.request.Request(
            PROPERTIES_URL,
            method="POST",
            data=b"{}",
            headers={"content-type": "application/json", "user-agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            props = json.loads(response.read().decode("utf-8"))["properties"]
    except Exception:
        props = _local_props()
    props["client_launch_id"] = str(uuid.uuid4())
    props["launch_signature"] = launch_signature
    props["client_heartbeat_session_id"] = heartbeat_session
    raw = json.dumps(props, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def verify_account(token: str, super_props: str) -> tuple[str, dict]:
    req = urllib.request.Request(ME_URL, headers={
        "authorization": token,
        "user-agent": USER_AGENT,
        "x-super-properties": super_props,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            analytics_token = data.get("analytics_token", "")
            if not analytics_token:
                raise ValueError("Missing analytics_token in Discord response.")
            return analytics_token, data
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ValueError("Invalid Discord token (HTTP 401).")
        raise ValueError(f"Discord error HTTP {exc.code}: {exc.reason}")
    except Exception as exc:
        raise ValueError(f"Connection failed: {str(exc)}")


# =========================================================================
# Multi-Account Slot Manager
# =========================================================================
class AccountSlot:
    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.token = ""
        self.cookie = ""
        self.user: Optional[dict] = None
        self.status = "empty" # "empty", "ready", "running", "stopping", "finished", "error"
        self.games_claimed = 0
        self.total_games = TARGET_GAMES_COUNT
        self.batches_sent = 0
        self.total_batches = (TARGET_GAMES_COUNT + BATCH_SIZE - 1) // BATCH_SIZE
        self.current_game = ""
        self.last_log = "Waiting for credentials"
        self.cancel_requested = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

    def to_dict(self) -> dict:
        pct = 0.0
        if self.total_games > 0:
            pct = round((self.games_claimed / self.total_games) * 100, 1)
        return {
            "slot_id": self.slot_id,
            "has_token": bool(self.token),
            "has_cookie": bool(self.cookie),
            "user": self.user,
            "status": self.status,
            "games_claimed": self.games_claimed,
            "total_games": self.total_games,
            "batches_sent": self.batches_sent,
            "total_batches": self.total_batches,
            "percent": pct,
            "current_game": self.current_game,
            "last_log": self.last_log
        }

    def clear(self):
        with self.lock:
            if self.status == "running":
                self.cancel_requested = True
            self.token = ""
            self.cookie = ""
            self.user = None
            self.status = "empty"
            self.games_claimed = 0
            self.batches_sent = 0
            self.current_game = ""
            self.last_log = "Slot cleared"

    def stop(self):
        with self.lock:
            if self.status == "running":
                self.cancel_requested = True
                self.status = "stopping"
                self.last_log = "Cancelling..."


class SlotManager:
    def __init__(self):
        self.slots: Dict[int, AccountSlot] = {i: AccountSlot(i) for i in range(1, MAX_SLOTS + 1)}
        self.clients: list[queue.Queue] = []
        self.clients_lock = threading.Lock()

    def broadcast(self, event_type: str, data: Any):
        msg = {"type": event_type, "timestamp": time.strftime("%H:%M:%S"), "data": data}
        with self.clients_lock:
            dead = []
            for q in self.clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for d in dead:
                if d in self.clients:
                    self.clients.remove(d)

    def register_client(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self.clients_lock:
            self.clients.append(q)
        return q

    def unregister_client(self, q: queue.Queue):
        with self.clients_lock:
            if q in self.clients:
                self.clients.remove(q)

    def get_summary(self) -> dict:
        all_slots = [slot.to_dict() for slot in self.slots.values()]
        active_count = sum(1 for s in self.slots.values() if s.status == "running")
        ready_count = sum(1 for s in self.slots.values() if s.status in ("ready", "running", "finished"))
        total_claimed = sum(s.games_claimed for s in self.slots.values())
        return {
            "slots": all_slots,
            "active_count": active_count,
            "ready_count": ready_count,
            "total_slots": MAX_SLOTS,
            "total_claimed": total_claimed,
            "target_per_account": TARGET_GAMES_COUNT
        }


MANAGER = SlotManager()

# =========================================================================
# Admin Portal & Key Licensing System Configuration
# =========================================================================
ADMIN_MASTER_KEY = os.environ.get(
    "ADMIN_KEY",
    "Cheeku_Bhen_ka_Lauda_ha_mera_choco_cheeku_ke_muh_me"
)

# In-memory admin session storage: session_token -> expiry_timestamp
ADMIN_SESSIONS: Dict[str, float] = {}
ADMIN_SESSION_LOCK = threading.Lock()
ADMIN_SESSION_TTL = 86400  # 24 hours

# Advanced Brute-Force Rate Limiting for Admin Portal:
# IP -> {"count": int, "locked_until": float, "attempts": list[float]}
FAILED_LOGIN_ATTEMPTS: Dict[str, dict] = {}
LOGIN_ATTEMPTS_LOCK = threading.Lock()
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes (in seconds)


def get_client_ip(req) -> str:
    """Extract real client IP safely, accounting for proxies."""
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return req.remote_addr or "127.0.0.1"


def check_login_lockout(ip: str) -> tuple[bool, int]:
    """Returns (is_locked, remaining_seconds)."""
    now = time.time()
    with LOGIN_ATTEMPTS_LOCK:
        entry = FAILED_LOGIN_ATTEMPTS.get(ip)
        if not entry:
            return False, 0
        locked_until = entry.get("locked_until", 0)
        if now < locked_until:
            return True, int(locked_until - now)
        if locked_until and now >= locked_until:
            FAILED_LOGIN_ATTEMPTS.pop(ip, None)
    return False, 0


def record_login_attempt(ip: str, success: bool):
    """Record attempt; resets on success, locks out after 5 consecutive failures."""
    now = time.time()
    with LOGIN_ATTEMPTS_LOCK:
        if success:
            FAILED_LOGIN_ATTEMPTS.pop(ip, None)
            return
        entry = FAILED_LOGIN_ATTEMPTS.setdefault(ip, {"count": 0, "locked_until": 0, "attempts": []})
        entry["attempts"].append(now)
        # Keep attempts inside 15-minute sliding window
        entry["attempts"] = [t for t in entry["attempts"] if now - t < 900]
        entry["count"] = len(entry["attempts"])
        if len(entry["attempts"]) >= MAX_FAILED_ATTEMPTS:
            entry["locked_until"] = now + LOCKOUT_DURATION


def create_admin_session() -> str:
    """Generate high-entropy 256-bit admin session token."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    with ADMIN_SESSION_LOCK:
        expired = [k for k, exp in ADMIN_SESSIONS.items() if now > exp]
        for k in expired:
            ADMIN_SESSIONS.pop(k, None)
        ADMIN_SESSIONS[token] = now + ADMIN_SESSION_TTL
    return token


def is_admin_authenticated(req) -> bool:
    """Authenticate admin session from header or cookie."""
    token = req.headers.get("X-Admin-Session") or req.cookies.get("a4ku_admin_session")
    if not token:
        auth_hdr = req.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    if not token:
        return False
    now = time.time()
    with ADMIN_SESSION_LOCK:
        exp = ADMIN_SESSIONS.get(token)
        if exp and now <= exp:
            return True
        if exp and now > exp:
            ADMIN_SESSIONS.pop(token, None)
    return False


@dataclass
class AccessKey:
    key: str
    created_at: float
    max_uses: int = 1
    uses_count: int = 0
    status: str = "active"  # "active", "used", "revoked"
    note: str = ""
    redemptions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "created_at": self.created_at,
            "max_uses": self.max_uses,
            "uses_count": self.uses_count,
            "status": self.status,
            "note": self.note,
            "redemptions": self.redemptions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AccessKey:
        return cls(
            key=data["key"],
            created_at=data.get("created_at", time.time()),
            max_uses=data.get("max_uses", 1),
            uses_count=data.get("uses_count", 0),
            status=data.get("status", "active"),
            note=data.get("note", ""),
            redemptions=data.get("redemptions", []),
        )


class KeyManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.lock = threading.Lock()
        self.keys: Dict[str, AccessKey] = {}
        self._load()

    def _load(self):
        with self.lock:
            if not self.storage_path.exists():
                self.keys = {}
                self._save_unlocked()
                return
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    key_list = raw.get("keys", [])
                    self.keys = {k["key"]: AccessKey.from_dict(k) for k in key_list}
            except Exception as exc:
                print(f"[KeyManager] Error loading {self.storage_path}: {exc}")
                self.keys = {}

    def _save_unlocked(self):
        try:
            temp_path = self.storage_path.with_suffix(".tmp")
            data = {"keys": [k.to_dict() for k in self.keys.values()]}
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.storage_path)
        except Exception as exc:
            print(f"[KeyManager] Error saving keys: {exc}")

    def _generate_key_unlocked(self) -> str:
        charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        for _ in range(100):
            p1 = "".join(secrets.choice(charset) for _ in range(4))
            p2 = "".join(secrets.choice(charset) for _ in range(4))
            p3 = "".join(secrets.choice(charset) for _ in range(4))
            candidate = f"{p1}-{p2}-{p3}"
            if candidate not in self.keys:
                return candidate
        return f"A4KU-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"

    def create_keys(self, count: int = 1, max_uses: int = 1, note: str = "") -> list[str]:
        count = max(1, min(count, 500))
        max_uses = max(1, min(max_uses, 999999))
        created = []
        with self.lock:
            now = time.time()
            for _ in range(count):
                k_str = self._generate_key_unlocked()
                key_obj = AccessKey(
                    key=k_str,
                    created_at=now,
                    max_uses=max_uses,
                    uses_count=0,
                    status="active",
                    note=note.strip()
                )
                self.keys[k_str] = key_obj
                created.append(k_str)
            self._save_unlocked()
        return created

    def update_key_uses(self, key_str: str, max_uses: int) -> bool:
        key_str = key_str.strip().upper()
        with self.lock:
            if key_str not in self.keys:
                return False
            k = self.keys[key_str]
            k.max_uses = max(1, min(max_uses, 999999))
            if k.status == "used" and k.uses_count < k.max_uses:
                k.status = "active"
            elif k.status == "active" and k.uses_count >= k.max_uses:
                k.status = "used"
            self._save_unlocked()
            return True

    def validate_key(self, key_str: str) -> tuple[bool, str, Optional[AccessKey]]:
        key_str = key_str.strip().upper()
        if not key_str:
            return False, "Access Key is required. Please paste your key to start badge farming.", None
        with self.lock:
            if key_str not in self.keys:
                return False, "Invalid Access Key. Please obtain a valid key from the Admin Portal.", None
            key_obj = self.keys[key_str]
            if key_obj.status == "revoked":
                return False, "This Access Key has been revoked by the administrator.", None
            if key_obj.uses_count >= key_obj.max_uses:
                return False, "This Access Key has already reached its maximum usage limit.", None
            return True, "", key_obj

    def record_redemption(self, key_str: str, user_id: str, username: str, ip: str, session_id: str) -> bool:
        key_str = key_str.strip().upper()
        with self.lock:
            if key_str not in self.keys:
                return False
            k = self.keys[key_str]
            k.uses_count += 1
            if k.uses_count >= k.max_uses:
                k.status = "used"
            k.redemptions.append({
                "user_id": user_id,
                "username": username,
                "timestamp": time.time(),
                "ip": ip or "Unknown",
                "session_id": session_id
            })
            self._save_unlocked()
            return True

    def revoke_key(self, key_str: str) -> bool:
        key_str = key_str.strip().upper()
        with self.lock:
            if key_str in self.keys:
                self.keys[key_str].status = "revoked"
                self._save_unlocked()
                return True
            return False

    def delete_key(self, key_str: str) -> bool:
        key_str = key_str.strip().upper()
        with self.lock:
            if key_str in self.keys:
                del self.keys[key_str]
                self._save_unlocked()
                return True
            return False

    def get_summary(self) -> dict:
        with self.lock:
            all_keys = list(self.keys.values())
            all_keys.sort(key=lambda x: x.created_at, reverse=True)
            active_count = sum(1 for k in all_keys if k.status == "active" and k.uses_count < k.max_uses)
            used_count = sum(1 for k in all_keys if k.uses_count >= k.max_uses or k.status == "used")
            revoked_count = sum(1 for k in all_keys if k.status == "revoked")
            total_redemptions = sum(len(k.redemptions) for k in all_keys)
            return {
                "total_keys": len(all_keys),
                "active_keys": active_count,
                "used_keys": used_count,
                "revoked_keys": revoked_count,
                "total_redemptions": total_redemptions,
                "keys": [k.to_dict() for k in all_keys]
            }


KEY_MANAGER = KeyManager(ROOT / "keys.json")


class QueueManager:
    def __init__(self, slot_manager: SlotManager):
        self.slot_manager = slot_manager
        self.active_sessions: Dict[str, int] = {}
        self.completed_sessions: Dict[str, dict] = {}
        self.waiting_queue: list[dict] = []
        self.lock = threading.Lock()

    def get_status(self):
        with self.lock:
            now = time.time()
            self.waiting_queue = [q for q in self.waiting_queue if (now - q.get("last_seen", now)) < 1800]
            active_count = sum(1 for s in self.slot_manager.slots.values() if s.status == "running")
            return {
                "activeCount": active_count,
                "queueLength": len(self.waiting_queue),
                "maxSlots": MAX_SLOTS,
                "availableSlots": max(0, MAX_SLOTS - active_count)
            }

    def join(self, session_id: str, token: str, cookie: str, key: str, ip: str = ""):
        with self.lock:
            now = time.time()
            self.waiting_queue = [q for q in self.waiting_queue if (now - q.get("last_seen", now)) < 1800]

            if session_id in self.active_sessions:
                slot_id = self.active_sessions[session_id]
                slot = self.slot_manager.slots[slot_id]
                if slot.status == "running":
                    return {"status": "active", "position": 0, "slot": slot.to_dict()}
                self.active_sessions.pop(session_id, None)
                slot.clear()

            # Clear any previously completed session record for this sessionId
            if session_id in self.completed_sessions:
                self.completed_sessions.pop(session_id, None)

            # Reconnection Safeguard: If this Discord token is ALREADY actively farming in a slot, seamlessly reconnect!
            for slot_obj in self.slot_manager.slots.values():
                if slot_obj.status == "running" and slot_obj.token == token:
                    self.active_sessions[session_id] = slot_obj.slot_id
                    return {"status": "active", "position": 0, "slot": slot_obj.to_dict()}

            # Reconnection Safeguard: If this Discord token already finished its 7,000 games run:
            token_h = hashlib.sha256(token.encode("utf-8")).hexdigest()
            for s_id, comp in list(self.completed_sessions.items()):
                if comp.get("token_hash") == token_h:
                    self.completed_sessions[session_id] = comp
                    return {"status": "completed", "position": 0, "slot": comp}

            # First: Validate access key before doing any work
            key_clean = key.strip().upper()
            if not key_clean:
                return {"status": "error", "error": "Access Key is required. Please paste your key to start badge farming."}
            is_valid, err_msg, _ = KEY_MANAGER.validate_key(key_clean)
            if not is_valid:
                return {"status": "error", "error": err_msg}

            for idx, item in enumerate(self.waiting_queue):
                if item["sessionId"] == session_id:
                    item["last_seen"] = now
                    return {"status": "waiting", "position": idx + 1, "activeCount": self._active_count(), "maxSlots": MAX_SLOTS}

            free_slot = self._find_free_slot()
            if free_slot and len(self.waiting_queue) == 0:
                err, udata = self._setup_and_start(free_slot, session_id, token, cookie, key_clean, ip)
                if err:
                    return {"status": "error", "error": err}
                return {"status": "active", "position": 0, "slot": free_slot.to_dict()}

            self.waiting_queue.append({
                "sessionId": session_id,
                "token": token,
                "cookie": cookie,
                "key": key_clean,
                "ip": ip,
                "joined_at": now,
                "last_seen": now
            })
            return {"status": "waiting", "position": len(self.waiting_queue), "activeCount": self._active_count(), "maxSlots": MAX_SLOTS}

    def poll(self, session_id: str):
        with self.lock:
            now = time.time()
            self.waiting_queue = [q for q in self.waiting_queue if (now - q.get("last_seen", now)) < 1800]

            if session_id in self.active_sessions:
                slot_id = self.active_sessions[session_id]
                slot = self.slot_manager.slots[slot_id]
                if slot.status == "finished":
                    return {
                        "status": "completed",
                        "position": 0,
                        "slot": slot.to_dict(),
                        "activeCount": self._active_count(),
                        "maxSlots": MAX_SLOTS
                    }
                return {
                    "status": "active",
                    "position": 0,
                    "slot": slot.to_dict(),
                    "activeCount": self._active_count(),
                    "maxSlots": MAX_SLOTS
                }

            # Check if this session completed while browser tab was closed
            if session_id in self.completed_sessions:
                comp_slot = self.completed_sessions[session_id]
                return {
                    "status": "completed",
                    "position": 0,
                    "slot": comp_slot,
                    "activeCount": self._active_count(),
                    "maxSlots": MAX_SLOTS
                }

            wait_idx = next((i for i, q in enumerate(self.waiting_queue) if q["sessionId"] == session_id), None)
            if wait_idx is not None:
                self.waiting_queue[wait_idx]["last_seen"] = now
                if wait_idx == 0:
                    free_slot = self._find_free_slot()
                    if free_slot:
                        item = self.waiting_queue.pop(0)
                        err, _ = self._setup_and_start(
                            free_slot,
                            item["sessionId"],
                            item["token"],
                            item["cookie"],
                            item.get("key", ""),
                            item.get("ip", "")
                        )
                        if not err:
                            return {"status": "active", "position": 0, "slot": free_slot.to_dict(), "activeCount": self._active_count(), "maxSlots": MAX_SLOTS}

                return {
                    "status": "waiting",
                    "position": wait_idx + 1,
                    "activeCount": self._active_count(),
                    "maxSlots": MAX_SLOTS,
                    "queueLength": len(self.waiting_queue)
                }

            return {"status": "idle", "activeCount": self._active_count(), "maxSlots": MAX_SLOTS}

    def record_completed_session(self, slot: AccountSlot):
        with self.lock:
            matched_sess = [s_id for s_id, s_num in self.active_sessions.items() if s_num == slot.slot_id]
            token_h = hashlib.sha256(slot.token.encode("utf-8")).hexdigest() if slot.token else ""
            for s_id in matched_sess:
                self.completed_sessions[s_id] = {
                    "slot_id": slot.slot_id,
                    "user": slot.user,
                    "games_claimed": slot.games_claimed,
                    "total_games": slot.total_games,
                    "status": "finished",
                    "finished_at": time.time(),
                    "last_log": slot.last_log,
                    "token_hash": token_h
                }

    def abort(self, session_id: str):
        with self.lock:
            if session_id in self.active_sessions:
                slot_id = self.active_sessions.pop(session_id)
                slot = self.slot_manager.slots[slot_id]
                slot.stop()
                slot.clear()
                self._check_queue_promotion()
                return {"status": "released"}

            if session_id in self.completed_sessions:
                self.completed_sessions.pop(session_id, None)

            self.waiting_queue = [q for q in self.waiting_queue if q["sessionId"] != session_id]
            return {"status": "released"}

    def _active_count(self):
        return sum(1 for s in self.slot_manager.slots.values() if s.status == "running")

    def _find_free_slot(self):
        for s in self.slot_manager.slots.values():
            if s.status != "running":
                return s
        return None

    def _setup_and_start(self, slot: AccountSlot, session_id: str, token: str, cookie: str, key: str = "", ip: str = ""):
        global GLOBAL_GAMES
        hb = str(uuid.uuid4())
        ls = str(uuid.uuid4())
        super_props = build_super_props(ls, hb)
        try:
            analytics_token, udata = verify_account(token, super_props)
        except Exception as exc:
            return str(exc), None

        # Verify succeeded: Record key redemption now (guarantees key isn't burned on bad Discord tokens)
        if key:
            KEY_MANAGER.record_redemption(
                key_str=key,
                user_id=udata.get("id", ""),
                username=udata.get("username", "User"),
                ip=ip,
                session_id=session_id
            )

        avatar_hash = udata.get("avatar")
        uid = udata.get("id", "")
        if avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png?size=128"
        else:
            discrim = int(udata.get("discriminator", 0)) % 5
            avatar_url = f"https://cdn.discordapp.com/embed/avatars/{discrim}.png"

        slot.token = token
        slot.cookie = cookie
        slot.user = {
            "id": uid,
            "username": udata.get("username", "User"),
            "global_name": udata.get("global_name") or udata.get("username"),
            "avatar_url": avatar_url
        }

        if not GLOBAL_GAMES:
            GLOBAL_GAMES = load_games_catalog()
        target_games = GLOBAL_GAMES[:TARGET_GAMES_COUNT]

        t = threading.Thread(target=slot_farming_worker, args=(slot, target_games), daemon=True)
        slot.thread = t
        t.start()

        self.active_sessions[session_id] = slot.slot_id
        return None, udata

    def _check_queue_promotion(self):
        if self.waiting_queue:
            free = self._find_free_slot()
            if free:
                next_item = self.waiting_queue.pop(0)
                self._setup_and_start(
                    free,
                    next_item["sessionId"],
                    next_item["token"],
                    next_item["cookie"],
                    next_item.get("key", ""),
                    next_item.get("ip", "")
                )


QUEUE_MANAGER = QueueManager(MANAGER)



# Worker thread function for each slot
def slot_farming_worker(slot: AccountSlot, games_subset: list[Game]):
    slot.status = "running"
    slot.cancel_requested = False
    slot.games_claimed = 0
    slot.batches_sent = 0
    slot.total_games = len(games_subset)
    slot.total_batches = (len(games_subset) + BATCH_SIZE - 1) // BATCH_SIZE
    slot.last_log = f"Authenticating slot {slot.slot_id}..."
    MANAGER.broadcast("slot_update", slot.to_dict())

    try:
        heartbeat_session = str(uuid.uuid4())
        launch_signature = str(uuid.uuid4())
        super_props = build_super_props(launch_signature, heartbeat_session)

        try:
            analytics_token, user_data = verify_account(slot.token, super_props)
        except Exception as exc:
            slot.status = "error"
            slot.last_log = f"Auth failed: {str(exc)}"
            MANAGER.broadcast("slot_update", slot.to_dict())
            return

        # Auto generate fingerprint for this account if on Windows
        user_id = user_data.get("id", "")
        fingerprint = generate_fingerprint_safe(user_id)

        # Each game gets 1 hour playtime automatically (3,600,000 ms)
        # This automatically satisfies BOTH badges:
        # 1) Total Games Played count badge (7,000 distinct games)
        # 2) Playtime Hours badge (7,000 hours claimed)
        duration_ms = 3600 * 1000
        seq = 0

        def next_seq():
            nonlocal seq
            seq += 1
            return seq

        chunks = [games_subset[i:i + BATCH_SIZE] for i in range(0, len(games_subset), BATCH_SIZE)]
        headers = {
            "accept": "*/*",
            "accept-language": "en-US",
            "authorization": slot.token,
            "content-type": "application/json",
            "cookie": slot.cookie,
            "origin": "https://discord.com",
            "referer": "https://discord.com/channels/@me",
            "user-agent": USER_AGENT,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "UTC",
            "x-super-properties": super_props,
        }

        for idx, chunk in enumerate(chunks, start=1):
            if slot.cancel_requested:
                slot.status = "ready"
                slot.last_log = "Stopped by user"
                MANAGER.broadcast("slot_update", slot.to_dict())
                return

            slot.current_game = chunk[0].name
            now = int(time.time() * 1000)
            events = []

            for g in chunk:
                sid = str(uuid.uuid4())
                start = now - duration_ms
                # 1. initial heartbeat
                events.append({
                    "type": "running_game_heartbeat",
                    "properties": {
                        "client_track_timestamp": start,
                        "client_heartbeat_session_id": heartbeat_session,
                        "event_sequence_number": next_seq(),
                        "game_id": g.id,
                        "game_name": g.name,
                        "game_executable": g.exe,
                        "initial_heartbeat": True,
                        "final_heartbeat": False,
                        "game_session_id": sid,
                        "duration_tracked_ms": 0,
                        "launch_signature": launch_signature,
                        "client_app_state": "focused",
                        "client_send_timestamp": start
                    }
                })
                # 2. launch game
                launch_props = {
                    "client_track_timestamp": now,
                    "client_heartbeat_session_id": heartbeat_session,
                    "event_sequence_number": next_seq(),
                    "game": g.name,
                    "game_id": g.id,
                    "verified": True,
                    "elevated": False,
                    "game_platform": "desktop",
                    "detection_method": "verified_game",
                    "executable_path": g.exe,
                    "launch_signature": launch_signature,
                    "client_app_state": "focused",
                    "client_send_timestamp": now
                }
                if fingerprint:
                    launch_props["executable_fingerprint"] = fingerprint
                events.append({"type": "launch_game", "properties": launch_props})
                # 3. closing heartbeat
                events.append({
                    "type": "running_game_heartbeat",
                    "properties": {
                        "client_track_timestamp": now,
                        "client_heartbeat_session_id": heartbeat_session,
                        "event_sequence_number": next_seq(),
                        "game_id": g.id,
                        "game_name": g.name,
                        "game_executable": g.exe,
                        "initial_heartbeat": False,
                        "final_heartbeat": True,
                        "game_session_id": sid,
                        "duration_tracked_ms": duration_ms,
                        "launch_signature": launch_signature,
                        "client_app_state": "focused",
                        "client_send_timestamp": now
                    }
                })

            payload = {"token": analytics_token, "events": events}
            body = json.dumps(payload).encode("utf-8")

            # Robust chunk retry loop: handles 429 rate limits and 502/503/504 gateway glitches
            max_chunk_retries = 5
            chunk_success = False

            for attempt in range(1, max_chunk_retries + 1):
                if slot.cancel_requested:
                    slot.status = "ready"
                    slot.last_log = "Stopped by user"
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    return

                req = urllib.request.Request(SCIENCE_URL, data=body, method="POST", headers=headers)
                status_code = 0
                try:
                    with urllib.request.urlopen(req, timeout=18) as resp:
                        status_code = resp.status
                except urllib.error.HTTPError as exc:
                    status_code = exc.code
                except Exception:
                    status_code = 0

                if status_code == 204:
                    slot.batches_sent += 1
                    slot.games_claimed += len(chunk)
                    slot.last_log = f"✓ Batch {idx}/{len(chunks)} OK ({slot.games_claimed}/{slot.total_games})"
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    chunk_success = True
                    break
                elif status_code in (401, 403):
                    slot.status = "error"
                    slot.last_log = f"✗ HTTP {status_code} Cookie/Auth expired. Update cf_clearance."
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    return
                elif status_code == 429:
                    retry_wait = min(10.0, 2.5 * attempt)
                    slot.last_log = f"⚠ Rate limited (429). Retrying batch {idx} in {int(retry_wait)}s (attempt {attempt}/{max_chunk_retries})..."
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    time.sleep(retry_wait)
                elif status_code in (500, 502, 503, 504) or status_code == 0:
                    retry_wait = min(8.0, 2.0 * attempt)
                    slot.last_log = f"⚠ Gateway error ({status_code or 'timeout'}). Retrying batch {idx} in {int(retry_wait)}s..."
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    time.sleep(retry_wait)
                else:
                    slot.last_log = f"⚠ Response {status_code}"
                    MANAGER.broadcast("slot_update", slot.to_dict())
                    break

            if not chunk_success and not slot.cancel_requested:
                slot.last_log = f"⚠ Batch {idx} incomplete after retries. Continuing..."
                MANAGER.broadcast("slot_update", slot.to_dict())

            time.sleep(BATCH_DELAY)

        slot.status = "finished"
        slot.last_log = f"🎉 7,000 Games Spoofed Successfully!"
        MANAGER.broadcast("slot_update", slot.to_dict())
        # Record session completion so user sees victory even if browser closed
        QUEUE_MANAGER.record_completed_session(slot)
    except Exception as exc:
        slot.status = "error"
        slot.last_log = f"Error: {str(exc)}"
        MANAGER.broadcast("slot_update", slot.to_dict())
    finally:
        QUEUE_MANAGER._check_queue_promotion()


# =========================================================================
# Web Application Server
# =========================================================================
app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
    static_url_path="/static"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/slots", methods=["GET"])
def get_slots():
    return jsonify(MANAGER.get_summary())


@app.route("/api/queue", methods=["GET", "POST", "OPTIONS"])
def handle_queue():
    if request.method == "OPTIONS":
        return "", 200

    data = request.get_json(silent=True) or {}
    action = data.get("action") or request.args.get("action", "status")
    session_id = data.get("sessionId") or request.args.get("sessionId", "")

    if action == "status":
        return jsonify(QUEUE_MANAGER.get_status())

    if not session_id:
        return jsonify({"error": "sessionId is required"}), 400

    if action == "join":
        token = data.get("token", "").strip()
        cookie = data.get("cookie", "").strip()
        key = data.get("key", "").strip()
        if not token:
            return jsonify({"status": "error", "error": "Token is required."}), 400
        if not cookie:
            return jsonify({"status": "error", "error": "cf_clearance cookie is required."}), 400
        if not key:
            return jsonify({"status": "error", "error": "Access Key is required. Please paste your key to start badge farming."}), 400
        client_ip = get_client_ip(request)
        res = QUEUE_MANAGER.join(session_id, token, cookie, key, client_ip)
        return jsonify(res)

    if action == "poll":
        return jsonify(QUEUE_MANAGER.poll(session_id))

    if action in ("leave", "abort"):
        return jsonify(QUEUE_MANAGER.abort(session_id))

    return jsonify({"error": f"Unknown action: {action}"}), 400


# =========================================================================
# Admin Portal & Key Tracking Routes
# =========================================================================
@app.route("/admin")
@app.route("/admin/")
def admin_portal():
    return render_template("admin.html")


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    client_ip = get_client_ip(request)
    is_locked, rem_secs = check_login_lockout(client_ip)
    if is_locked:
        return jsonify({
            "success": False,
            "error": f"Security Lockout: Too many failed login attempts. Try again in {rem_secs} seconds."
        }), 429

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if not password:
        record_login_attempt(client_ip, False)
        return jsonify({"success": False, "error": "Master security key is required."}), 400

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(password.encode("utf-8"), ADMIN_MASTER_KEY.encode("utf-8")):
        record_login_attempt(client_ip, False)
        with LOGIN_ATTEMPTS_LOCK:
            entry = FAILED_LOGIN_ATTEMPTS.get(client_ip, {})
            rem_attempts = max(0, MAX_FAILED_ATTEMPTS - len(entry.get("attempts", [])))
        return jsonify({
            "success": False,
            "error": f"Invalid Master Security Key. ({rem_attempts} attempts remaining before 15-minute IP lockout)."
        }), 401

    # Successful login: reset brute-force counters and create session
    record_login_attempt(client_ip, True)
    session_token = create_admin_session()
    resp = jsonify({"success": True, "token": session_token})
    resp.set_cookie("a4ku_admin_session", session_token, httponly=True, samesite="Strict", max_age=86400)
    return resp


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    token = request.headers.get("X-Admin-Session") or request.cookies.get("a4ku_admin_session")
    if token:
        with ADMIN_SESSION_LOCK:
            ADMIN_SESSIONS.pop(token, None)
    resp = jsonify({"success": True})
    resp.delete_cookie("a4ku_admin_session")
    return resp


@app.route("/api/admin/overview", methods=["GET"])
def admin_overview():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized. Please authenticate with Admin Master Key."}), 401

    summary = KEY_MANAGER.get_summary()
    slots_info = MANAGER.get_summary()["slots"]
    queue_info = QUEUE_MANAGER.get_status()

    return jsonify({
        "success": True,
        "metrics": {
            "total_keys": summary["total_keys"],
            "active_keys": summary["active_keys"],
            "used_keys": summary["used_keys"],
            "revoked_keys": summary["revoked_keys"],
            "total_redemptions": summary["total_redemptions"],
            "active_slots": queue_info["activeCount"],
            "max_slots": MAX_SLOTS,
            "queue_length": queue_info["queueLength"]
        },
        "keys": summary["keys"],
        "slots": slots_info,
        "queue": queue_info
    })


@app.route("/api/admin/keys/create", methods=["POST"])
def admin_create_keys():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        count = int(data.get("count", 1))
    except (ValueError, TypeError):
        count = 1
    try:
        max_uses = int(data.get("max_uses", 1))
    except (ValueError, TypeError):
        max_uses = 1
    note = str(data.get("note", "")).strip()

    new_keys = KEY_MANAGER.create_keys(count=count, max_uses=max_uses, note=note)
    return jsonify({"success": True, "keys": new_keys, "count": len(new_keys)})


@app.route("/api/admin/keys/revoke", methods=["POST"])
def admin_revoke_key():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key_str = data.get("key", "").strip()
    ok = KEY_MANAGER.revoke_key(key_str)
    return jsonify({"success": ok})


@app.route("/api/admin/keys/delete", methods=["POST"])
def admin_delete_key():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key_str = data.get("key", "").strip()
    ok = KEY_MANAGER.delete_key(key_str)
    return jsonify({"success": ok})


@app.route("/api/admin/keys/update_uses", methods=["POST"])
def admin_update_key_uses():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key_str = data.get("key", "").strip()
    try:
        max_uses = int(data.get("max_uses", 1))
    except (ValueError, TypeError):
        max_uses = 1
    ok = KEY_MANAGER.update_key_uses(key_str, max_uses)
    if ok:
        return jsonify({"success": True, "message": f"Key {key_str} updated to {max_uses} uses."})
    return jsonify({"error": "Key not found"}), 404


@app.route("/api/admin/slot/stop", methods=["POST"])
def admin_stop_slot():
    if not is_admin_authenticated(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    slot_id = int(data.get("slot_id", 0))
    if slot_id in MANAGER.slots:
        slot = MANAGER.slots[slot_id]
        slot.stop()
        slot.clear()
        MANAGER.broadcast("slot_update", slot.to_dict())
        QUEUE_MANAGER._check_queue_promotion()
        return jsonify({"success": True, "message": f"Slot #{slot_id} stopped and cleared."})
    return jsonify({"error": "Invalid slot_id"}), 400



@app.route("/api/slot/<int:slot_id>/set", methods=["POST"])
def set_slot(slot_id: int):
    if slot_id not in MANAGER.slots:
        return jsonify({"error": "Invalid slot ID"}), 400
    slot = MANAGER.slots[slot_id]

    payload = request.get_json(silent=True) or {}
    token = payload.get("token", "").strip()
    cookie = payload.get("cookie", "").strip()

    if not token:
        return jsonify({"error": "Discord token is required"}), 400

    slot.token = token
    slot.cookie = cookie

    # Verify token
    try:
        hb = str(uuid.uuid4())
        ls = str(uuid.uuid4())
        super_props = build_super_props(ls, hb)
        analytics_token, udata = verify_account(token, super_props)

        avatar_hash = udata.get("avatar")
        uid = udata.get("id", "")
        if avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png?size=128"
        else:
            discrim = int(udata.get("discriminator", 0)) % 5
            avatar_url = f"https://cdn.discordapp.com/embed/avatars/{discrim}.png"

        slot.user = {
            "id": uid,
            "username": udata.get("username", "User"),
            "global_name": udata.get("global_name") or udata.get("username"),
            "avatar_url": avatar_url
        }
        slot.status = "ready"
        slot.last_log = f"Ready: @{udata.get('username')}"
        MANAGER.broadcast("slot_update", slot.to_dict())
        return jsonify({"success": True, "slot": slot.to_dict()})
    except Exception as exc:
        slot.status = "error"
        slot.last_log = f"Invalid Token: {str(exc)}"
        MANAGER.broadcast("slot_update", slot.to_dict())
        return jsonify({"success": False, "error": str(exc), "slot": slot.to_dict()})


@app.route("/api/slot/<int:slot_id>/clear", methods=["POST"])
def clear_slot(slot_id: int):
    if slot_id in MANAGER.slots:
        MANAGER.slots[slot_id].clear()
        MANAGER.broadcast("slot_update", MANAGER.slots[slot_id].to_dict())
    return jsonify({"success": True})


@app.route("/api/slot/<int:slot_id>/start", methods=["POST"])
def start_single_slot(slot_id: int):
    global GLOBAL_GAMES
    if slot_id not in MANAGER.slots:
        return jsonify({"error": "Invalid slot ID"}), 400
    slot = MANAGER.slots[slot_id]

    if not slot.token or not slot.cookie:
        return jsonify({"error": "Both Token and Cookie are required to farm."}), 400
    if slot.status == "running":
        return jsonify({"error": "Slot is already running."}), 409

    if not GLOBAL_GAMES:
        GLOBAL_GAMES = load_games_catalog()

    target_games = GLOBAL_GAMES[:TARGET_GAMES_COUNT]
    thread = threading.Thread(target=slot_farming_worker, args=(slot, target_games), daemon=True)
    slot.thread = thread
    thread.start()

    return jsonify({"success": True, "message": f"Slot #{slot_id} started (7,000 games automatic)."})


@app.route("/api/slot/<int:slot_id>/stop", methods=["POST"])
def stop_single_slot(slot_id: int):
    if slot_id in MANAGER.slots:
        MANAGER.slots[slot_id].stop()
        MANAGER.broadcast("slot_update", MANAGER.slots[slot_id].to_dict())
    return jsonify({"success": True})


@app.route("/api/start-all", methods=["POST"])
def start_all():
    global GLOBAL_GAMES
    if not GLOBAL_GAMES:
        GLOBAL_GAMES = load_games_catalog()
    target_games = GLOBAL_GAMES[:TARGET_GAMES_COUNT]

    started = 0
    for slot in MANAGER.slots.values():
        if slot.token and slot.cookie and slot.status != "running":
            t = threading.Thread(target=slot_farming_worker, args=(slot, target_games), daemon=True)
            slot.thread = t
            t.start()
            started += 1

    return jsonify({"success": True, "started_count": started})


@app.route("/api/stop-all", methods=["POST"])
def stop_all():
    stopped = 0
    for slot in MANAGER.slots.values():
        if slot.status == "running":
            slot.stop()
            stopped += 1
    return jsonify({"success": True, "stopped_count": stopped})


@app.route("/api/bulk-import", methods=["POST"])
def bulk_import():
    payload = request.get_json(silent=True) or {}
    raw_text = payload.get("text", "").strip()
    if not raw_text:
        return jsonify({"error": "Empty import text"}), 400

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    pairs = []
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            pairs.append((parts[0].strip(), parts[1].strip()))
        elif "|" in line:
            parts = line.split("|", 1)
            pairs.append((parts[0].strip(), parts[1].strip()))

    imported = 0
    for idx, (tok, cook) in enumerate(pairs[:MAX_SLOTS], start=1):
        slot = MANAGER.slots[idx]
        slot.token = tok
        slot.cookie = cook
        try:
            hb = str(uuid.uuid4())
            ls = str(uuid.uuid4())
            _, udata = verify_account(tok, build_super_props(ls, hb))
            avatar_hash = udata.get("avatar")
            uid = udata.get("id", "")
            avatar_url = (f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.png?size=128"
                          if avatar_hash else f"https://cdn.discordapp.com/embed/avatars/0.png")
            slot.user = {"id": uid, "username": udata.get("username"), "global_name": udata.get("global_name"), "avatar_url": avatar_url}
            slot.status = "ready"
            slot.last_log = f"Ready: @{udata.get('username')}"
        except Exception as exc:
            slot.status = "ready" if (tok and cook) else "empty"
            slot.last_log = "Added (Unverified)"
        imported += 1
        MANAGER.broadcast("slot_update", slot.to_dict())

    return jsonify({"success": True, "imported_count": imported})


@app.route("/api/events")
def stream_events():
    q = MANAGER.register_client()

    def stream() -> Generator[str, None, None]:
        init_data = json.dumps({"type": "init", "summary": MANAGER.get_summary()})
        yield f"data: {init_data}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=20.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            MANAGER.unregister_client(q)

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )


def run_web(host=None, port=None):
    if host is None:
        host = os.environ.get("HOST", "0.0.0.0")
    if port is None:
        port = int(os.environ.get("PORT", 5000))
    _ensure_games_loaded()
    print(f"Catalog ready: {len(GLOBAL_GAMES)} total games. (Target: {TARGET_GAMES_COUNT} games/slot).")
    print(f"Discord 7K Spoofer Web Server running at: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_web()
