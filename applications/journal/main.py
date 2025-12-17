#!/usr/bin/env python3

from adafruit_atecc.adafruit_atecc import ATECC
import helpers

try:
    atecc = ATECC(helpers.i2c)
except Exception:
    print("ATECC not initialized. Exiting.")
    raise SystemExit(1)

printf("Decrypting journal entries...")

import json
import time
import binascii
import hmac as _hmac
from secureCore import ChaCha20Poly1305
from ellipticcurve.privateKey import PrivateKey
import ellipticcurve.curve as curve
import os
import editor
import usb.core
import adafruit_usb_host_mass_storage
import adafruit_usb_host_descriptors
import storage

PROGRAM_FOLDER = "sd/usr/journal"
METADATA_FILE = "sd/usr/journal/metadata.dat"
METADATA_KDF_PUBKEY_FILE = "sd/usr/journal/metadata_kdf_pub.hex"
WRAP_WIDTH = helpers.MAX_CHARS_WIDTH

MAGIC_META_V1 = b"M1"
MAGIC_ENTRY_V1 = b"J1"

def my_join_path(*parts):
    if not parts:
        return ''
    path = parts[0]
    for p in parts[1:]:
        if path.endswith('/'):
            path += p.lstrip('/')
        else:
            path += '/' + p.lstrip('/')
    return path

def my_dir_exists(path):
    try:
        import uos as os
    except ImportError:
        import os
    try:
        return os.stat(path)[0] & 0x4000
    except Exception:
        return False

def my_file_exists(path):
    try:
        import uos as os
    except ImportError:
        import os
    try:
        os.stat(path)
        return True
    except Exception:
        return False

def my_mkdir(path):
    try:
        import uos as os
    except ImportError:
        import os
    try:
        os.mkdir(path)
    except Exception:
        pass

def _hkdf(secret, info):
    return _hmac.new_hmac(secret, info).digest()

def _os_nonce(n=12):
    try:
        import urandom
        return bytes([urandom.getrandbits(8) for _ in range(n)])
    except Exception:
        import os
        return os.urandom(n)

if not my_dir_exists(PROGRAM_FOLDER):
    my_mkdir(PROGRAM_FOLDER)

if not my_file_exists(METADATA_KDF_PUBKEY_FILE):
    _priv = PrivateKey(curve=curve.prime256v1)
    _pub_hex = _priv.publicKey().toString()
    with open(METADATA_KDF_PUBKEY_FILE, "w") as f:
        f.write(_pub_hex)

with open(METADATA_KDF_PUBKEY_FILE, "r") as f:
    _METADATA_PUB_HEX = f.read().strip()

try:
    atecc.wakeup()
except Exception:
    pass

_SESSION_META_KEY = _hkdf(atecc.ecdh(1, bytearray.fromhex(_METADATA_PUB_HEX)), b"journal-metadata-v1")

def meta_encrypt(plaintext):
    nonce = _os_nonce(12)
    cipher = ChaCha20Poly1305(_SESSION_META_KEY)
    ct = cipher.encrypt(nonce, plaintext, None)
    return MAGIC_META_V1 + nonce + ct

def meta_decrypt(blob):
    if not blob.startswith(MAGIC_META_V1):
        raise ValueError("metadata format not recognized (missing M1 magic)")
    nonce = blob[2:14]
    ct = blob[14:]
    cipher = ChaCha20Poly1305(_SESSION_META_KEY)
    return cipher.decrypt(nonce, ct, None)

def entry_encrypt(plaintext):
    eph_priv = PrivateKey(curve=curve.prime256v1)
    eph_pub_bytes = bytearray.fromhex(eph_priv.publicKey().toString())
    try:
        atecc.wakeup()
    except Exception:
        pass
    shared = atecc.ecdh(1, eph_pub_bytes)
    key = _hkdf(shared, b"journal-entry-v1")
    nonce = _os_nonce(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)
    return MAGIC_ENTRY_V1 + nonce + eph_pub_bytes + ct

def entry_decrypt(blob):
    if not blob.startswith(MAGIC_ENTRY_V1):
        raise ValueError("entry format not recognized (missing J1 magic)")
    nonce = blob[2:14]
    eph_pub = blob[14:78]
    ct = blob[78:]
    try:
        atecc.wakeup()
    except Exception:
        pass
    shared = atecc.ecdh(1, bytearray(eph_pub))
    key = _hkdf(shared, b"journal-entry-v1")
    return ChaCha20Poly1305(key).decrypt(nonce, ct, None)

def format_struct_time(t):
    """Format a time.struct_time into '%A, %B %-d, %Y %-I:%M %p' format."""
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # Extract fields
    year = t.tm_year
    month = months[t.tm_mon - 1]
    day = t.tm_mday
    weekday = weekdays[t.tm_wday]

    hour_24 = t.tm_hour
    minute = t.tm_min

    # Convert to 12-hour format
    if hour_24 == 0:
        hour_12 = 12
        ampm = "AM"
    elif hour_24 < 12:
        hour_12 = hour_24
        ampm = "AM"
    elif hour_24 == 12:
        hour_12 = 12
        ampm = "PM"
    else:
        hour_12 = hour_24 - 12
        ampm = "PM"

    # Build string
    return f"{weekday}, {month} {day}, {year} {hour_12}:{minute:02d} {ampm}"

def _looks_hex_ascii(data):
    if not data:
        return False
    try:
        _ = data.decode("ascii")
    except Exception:
        return False
    hexdigits = set(b"0123456789abcdefABCDEF\n\r ")
    return all(ch in hexdigits for ch in data)

def _decrypt_legacy_hex(data_hex_ascii):
    raw = bytearray.fromhex(data_hex_ascii.decode("ascii").strip())
    nonce = raw[:12]
    eph_pub = raw[12:12+64]
    ct = raw[12+64:]
    try:
        atecc.wakeup()
    except Exception:
        pass
    shared = atecc.ecdh(1, bytearray(eph_pub))
    key = _hkdf(shared, b"journal-v1")
    return ChaCha20Poly1305(key).decrypt(nonce, ct, None)

_METADATA_CACHE = {}

def _load_metadata_into_cache():
    global _METADATA_CACHE
    if not my_file_exists(METADATA_FILE):
        with open(METADATA_FILE, "wb") as f:
            f.write(meta_encrypt(b"{}"))
        _METADATA_CACHE = {}
        return
    with open(METADATA_FILE, "rb") as f:
        blob = f.read()
    if _looks_hex_ascii(blob):
        plaintext = _decrypt_legacy_hex(blob)
        try:
            _METADATA_CACHE = json.loads(plaintext.decode("utf-8"))
        except Exception:
            _METADATA_CACHE = {}
        with open(METADATA_FILE, "wb") as wf:
            wf.write(meta_encrypt(json.dumps(_METADATA_CACHE).encode("utf-8")))
        return
    plaintext = meta_decrypt(blob)
    try:
        _METADATA_CACHE = json.loads(plaintext.decode("utf-8"))
    except Exception:
        _METADATA_CACHE = {}

def _flush_metadata_cache():
    with open(METADATA_FILE, "wb") as f:
        f.write(meta_encrypt(json.dumps(_METADATA_CACHE, separators=(",", ":")).encode("utf-8")))

def read_metadata():
    return _METADATA_CACHE

def append_metadata(delta):
    _METADATA_CACHE.update(delta)
    _flush_metadata_cache()

def print_header(title):
    print("\n" + "=" * WRAP_WIDTH)
    print(title)
    print("=" * WRAP_WIDTH)

def read_line(prompt, default=None):
    s = input(prompt).strip()
    if not s and default is not None:
        return default
    return s

def read_multiline(prompt):
    print(prompt)
    print("(Finish with a single '.' on its own line)")
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()

def count_words(text):
    return len(text.split())

def copy_file(src, dst, buf_size=4096):
    with open(src, "rb") as f_src, open(dst, "wb") as f_dst:
        while True:
            buf = f_src.read(buf_size)
            if not buf:
                break
            f_dst.write(buf)

# Menu functions

def action_new():
    print_header("New Entry")
    title, body = editor.get("Title: ")
    helpers.cls()
    if title == None and body == None:
        return
        
    print("Encrypting...")

    filename = binascii.hexlify(_os_nonce(32)).decode("utf-8") + ".dat"
    entry_meta = {
        filename: {
            "title": title,
            "time": time.time(),
            "words": count_words(body)
        }
    }
    append_metadata(entry_meta)
    with open(my_join_path(PROGRAM_FOLDER, filename), "wb") as f:
        f.write(entry_encrypt(body.encode("utf-8")))
    print("Saved successfully. Returning to menu...")

def action_list():
    md = read_metadata()
    num_entries = len(md)
    options = []
    try:
        tz_offset = float(os.getenv("TZ_OFFSET", "0"))
    except Exception:
        tz_offset = 0.0
    offset_seconds = int(tz_offset * 3600)
    opDict = {}
    for filename, entry in sorted(md.items(), key=lambda kv: kv[1].get("time", 0), reverse=True):
        local_timestamp = entry.get("time", 0) + offset_seconds
        t = time.localtime(local_timestamp)
        formatted = format_struct_time(t)
        t = entry.get("title", None)
        if t:
            fstring = f' - "{t}" - {formatted} (Words: {entry.get('words', 0)})'
        else:
            fstring = f' - Untitled - {formatted} (Words: {entry.get('words', 0)})'
        options.append(fstring)
        opDict[fstring] = filename
    selected = helpers.select(options, f"List Entries ({num_entries})")
    with open(my_join_path(PROGRAM_FOLDER, opDict[selected]), "rb") as f:
        data = entry_decrypt(f.read())
    print_header(selected[3:])
    print(data.decode("utf-8"))
    print("\n" + ("=" * WRAP_WIDTH))
    helpers.pause()
    helpers.cls()

def action_search():
    print_header("Search (EMPTY)")
    _q = read_line("Keyword or '#tag': ")
    print("TODO: Implement search logic against your storage backend.")

def action_stats():
    print_header("Stats")
    md = read_metadata()
    total_entries = len(md)
    total_words = sum(int(v.get("words", 0)) for v in md.values())
    print(f"Total entries: {total_entries}")
    print(f"Total words: {total_words}")
    if total_entries > 0:
        print(f"Average words per entry: {total_words // total_entries}")

def action_export():
    print_header("Export to USB Mass Storage")

    msDevice = None
    while msDevice is None:
        printf("Searching for mass storage endpoints...")
        for device in usb.core.find(find_all=True):
            massStorageEndpoint = adafruit_usb_host_descriptors.find_mass_storage_endpoints(device)[0]
            if massStorageEndpoint != None:
                msDevice = device
            
        if not msDevice:
            printf("Couldn't find a storage endpoint... retrying")
            time.sleep(5)

    printf("Now exporting...")

    msc = adafruit_usb_host_mass_storage.USBMassStorage(msDevice)
    vfs = storage.VfsFat(msc)
    storage.mount(vfs, "/usb_media")

    print("Mounted")

    if not my_dir_exists("/usb_media/JOURNAL_EXPORT"):
        os.mkdir("/usb_media/JOURNAL_EXPORT")
    

    printf("Exporting metadata...")
    copy_file(METADATA_FILE, f"/usb_media/JOURNAL_EXPORT/metadata.dat")
    printf("Exported metadata.")

    lenMetadata = len(_METADATA_CACHE)
    i = 0

    for file in _METADATA_CACHE:
        copy_file(f"{PROGRAM_FOLDER}/{file}", f"/usb_media/JOURNAL_EXPORT/{file}")
        i += 1
        printf(f"Copied entry {i}/{lenMetadata}")

    storage.umount(vfs)
    
    printf("Exported all entries to USB Mass Storage device")

MENU_ITEMS = [
    ("New entry", action_new),
    ("List entries", action_list),
    ("Search", action_search),
    ("Stats", action_stats),
    ("Export to USB Storage", action_export),
    ("Clear screen", lambda: print("\n" * 60)),
    ("Quit", None),
]

def print_menu():
    print_header("Journal")
    for i, (label, _) in enumerate(MENU_ITEMS, start=1):
        print(f"{i}. {label}")

def main():
    _load_metadata_into_cache()
    while True:
        print_menu()
        choice = input("Select an option: ").strip()
        if not choice.isdigit():
            print("Enter a number from the menu.")
            continue
        idx = int(choice) - 1
        if idx < 0 or idx >= len(MENU_ITEMS):
            print("Invalid choice.")
            continue
        label, func = MENU_ITEMS[idx]
        if func is None:
            print("Goodbye!")
            break
        try:
            helpers.cls()
        except Exception:
            pass
        func()

main()