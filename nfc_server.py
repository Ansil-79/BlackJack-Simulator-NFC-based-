"""
NFC Tap-to-Pay WebSocket Server
================================
Reads balance from NFC chip, handles write-back after wins.

Chip format (plain text NDEF):
  "BALANCE:250"   →  player has $250

pip3 install pyscard websockets
python3 nfc_server.py
"""

import asyncio
import json
import threading
import time
from datetime import datetime

import websockets
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.util import toHexString


# ── State ────────────────────────────────────────────────────────────────────
connected_clients: set = set()
nfc_queue: asyncio.Queue = None
event_loop = None

# Modes the server can be in
MODE_READ  = "read"   # waiting for tap to read balance
MODE_WRITE = "write"  # waiting for tap to write new balance back
pending_write_balance = None  # balance to write on next tap


# ── NDEF helpers ─────────────────────────────────────────────────────────────
def read_pages(connection):
    raw = bytearray()
    for page in range(4, 40):
        data, sw1, _ = connection.transmit([0xFF, 0xB0, 0x00, page, 0x04])
        if sw1 == 0x90:
            raw.extend(data)
        else:
            break
    return bytes(raw)


def parse_ndef_text(raw):
    i = 0
    while i < len(raw):
        if raw[i] == 0x00: i += 1; continue
        if raw[i] == 0xFE: break
        tag = raw[i]; i += 1
        length = raw[i]; i += 1
        if tag != 0x03: i += length; continue
        ndef = raw[i: i + length]
        j = 0
        while j < len(ndef):
            flags = ndef[j]; j += 1
            tlen  = ndef[j]; j += 1
            sr    = (flags >> 4) & 1
            plen  = ndef[j] if sr else int.from_bytes(ndef[j:j+4], 'big')
            j    += 1 if sr else 4
            rtype = ndef[j: j + tlen]; j += tlen
            pay   = ndef[j: j + plen]; j += plen
            if (flags & 7) == 1 and rtype == b'T' and len(pay) > 1:
                lang_len = pay[0] & 0x3F
                return pay[1 + lang_len:].decode("utf-8", errors="replace")
        i += length
    return None


def build_ndef_text_record(text: str) -> bytes:
    """Build a minimal NDEF Text record for writing back to the chip."""
    lang = b'en'
    payload = bytes([len(lang)]) + lang + text.encode('utf-8')
    # NDEF record: TNF=0x01 (Well-known), SR=1, type='T'
    record = bytes([
        0xD1,           # MB=1, ME=1, SR=1, TNF=Well-known
        0x01,           # Type length = 1
        len(payload),   # Payload length
        0x54,           # Type = 'T' (Text)
    ]) + payload
    # Wrap in TLV: 0x03 <len> <ndef> 0xFE
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    # Pad to page boundary (4 bytes)
    while len(tlv) % 4 != 0:
        tlv += b'\x00'
    return tlv


def write_pages(connection, data: bytes) -> bool:
    """Write data to chip starting at page 4."""
    for i in range(0, len(data), 4):
        page = 4 + (i // 4)
        chunk = list(data[i:i+4])
        if len(chunk) < 4:
            chunk += [0] * (4 - len(chunk))
        cmd = [0xFF, 0xD6, 0x00, page, 0x04] + chunk
        _, sw1, sw2 = connection.transmit(cmd)
        if sw1 != 0x90:
            return False
    return True


# ── NFC Observer ─────────────────────────────────────────────────────────────
class NFCObserver(CardObserver):
    def update(self, observable, actions):
        global pending_write_balance, event_loop, nfc_queue

        cards_tapped = actions[0]
        if not cards_tapped:
            return

        card = cards_tapped[0]
        try:
            conn = card.createConnection()
            conn.connect()

            if pending_write_balance is not None:
                # WRITE MODE — write new balance back to chip
                balance = pending_write_balance
                text = f"BALANCE:{balance}"
                data = build_ndef_text_record(text)
                success = write_pages(conn, data)
                event = {
                    "type": "write_result",
                    "success": success,
                    "balance": balance,
                    "timestamp": datetime.now().isoformat()
                }
                pending_write_balance = None
            else:
                # READ MODE — read balance from chip
                raw  = read_pages(conn)
                text = parse_ndef_text(raw)
                balance = None
                if text and text.startswith("BALANCE:"):
                    try:
                        balance = int(text.split(":")[1].strip())
                    except ValueError:
                        balance = None
                event = {
                    "type": "card_read",
                    "raw_text": text,
                    "balance": balance,
                    "timestamp": datetime.now().isoformat()
                }

            asyncio.run_coroutine_threadsafe(nfc_queue.put(event), event_loop)

        except Exception as e:
            event = {"type": "error", "message": str(e)}
            asyncio.run_coroutine_threadsafe(nfc_queue.put(event), event_loop)


# ── WebSocket handlers ────────────────────────────────────────────────────────
async def handler(websocket):
    connected_clients.add(websocket)
    print(f"[+] Client connected ({len(connected_clients)} total)")
    try:
        async for message in websocket:
            data = json.loads(message)
            await handle_client_message(data)
    except websockets.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[-] Client disconnected ({len(connected_clients)} total)")


async def handle_client_message(data):
    global pending_write_balance
    if data.get("type") == "prepare_write":
        pending_write_balance = data.get("balance")
        print(f"[write] Pending write: BALANCE:{pending_write_balance}")


async def broadcast(event):
    if not connected_clients:
        return
    msg = json.dumps(event)
    await asyncio.gather(*[c.send(msg) for c in list(connected_clients)], return_exceptions=True)


async def queue_loop():
    while True:
        event = await nfc_queue.get()
        print(f"[nfc] {event}")
        await broadcast(event)


# ── Main ─────────────────────────────────────────────────────────────────────
async def main():
    global nfc_queue, event_loop
    event_loop = asyncio.get_running_loop()
    nfc_queue  = asyncio.Queue()

    monitor = CardMonitor()
    monitor.addObserver(NFCObserver())
    print("NFC reader ready (pyscard)")

    async with websockets.serve(handler, "localhost", 8765):
        print("WebSocket server on ws://localhost:8765")
        print("Open index.html in your browser\n")
        await queue_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
