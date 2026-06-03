"""
NFC Reader — ACR122U-A9
pip3 install pyscard
python3 nfc_read.py
"""

from smartcard.CardMonitoring import CardMonitor, CardObserver
import time


def read_text(connection):
    raw = bytearray()
    for page in range(4, 40):
        data, sw1, _ = connection.transmit([0xFF, 0xB0, 0x00, page, 0x04])
        if sw1 == 0x90:
            raw.extend(data)
        else:
            break
    return parse_ndef(bytes(raw))


def parse_ndef(raw):
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
            plen  = ndef[j] if (flags >> 4) & 1 else int.from_bytes(ndef[j:j+4], 'big')
            j    += 1 if (flags >> 4) & 1 else 4
            rtype = ndef[j: j + tlen]; j += tlen
            pay   = ndef[j: j + plen]; j += plen
            if (flags & 7) == 1 and rtype == b'T' and len(pay) > 1:
                return pay[1 + (pay[0] & 0x3F):].decode("utf-8", errors="replace")
        i += length
    return None


class Reader(CardObserver):
    def update(self, observable, actions):
        for card in actions[0]:
            try:
                conn = card.createConnection()
                conn.connect()
                text = read_text(conn)
                print(f"\n  Text: {text or '(no text on chip)'}\n")
            except Exception as e:
                print(f"  Error: {e}")


print("Ready — tap your chip to the reader  (Ctrl+C to stop)\n")
monitor = CardMonitor()
monitor.addObserver(Reader())
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    print("Stopped.")