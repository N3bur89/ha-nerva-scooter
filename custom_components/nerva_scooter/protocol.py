"""Protocollo BLE "SZHY" dell'app Nerva (ricavato dal codice dell'app).

Richiesta:  'SZHY' 01 <len> 00 00 00 <id> <VIN 17 ascii> <modello 2 byte> <checksum>
Risposta:   frame da 139 byte, 'SZHY' 02 ... ; byte[9]==1; byte[138]=somma(byte[0:138]) & 0xFF
"""
from __future__ import annotations

import re

HEADER = b"SZHY"
FRAME_LEN = 139
VIN_RE = re.compile(r"^[0-9A-Z]{17}$")

# id comando -> (lunghezza, codice) ; dalla tabella cmd_section dell'app
CMD_VEHICLE_INFO = (0x1E, 0x46)  # comando "13"
CMD_VIN = (0x1E, 0x47)  # comando "28"
CMD_VERSION = (0x1E, 0x38)  # comando "16"
CMD_BIND = (0x26, 0x4E)  # comando "05": associazione con password app (8 caratteri)
BIND_REPLY_CODE = 0x4F  # risposta comando "06": ... VIN, 0xAA=ok / 0x55=rifiutato, modello


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_command(cmd: tuple[int, int], vin: str, model: str) -> bytes:
    length, code = cmd
    body = HEADER + b"\x01" + bytes([length]) + b"\x00\x00\x00" + bytes([code])
    body += vin.encode("ascii") + bytes.fromhex(model)
    return body + bytes([checksum(body)])


def build_bind(vin: str, password: str, model: str) -> bytes:
    """Comando di associazione (come "firstbinding" dell'app)."""
    length, code = CMD_BIND
    body = HEADER + b"\x01" + bytes([length]) + b"\x00\x00\x00" + bytes([code])
    body += vin.encode("ascii") + password.encode("ascii") + bytes.fromhex(model)
    return body + bytes([checksum(body)])


def parse_bind_reply(data: bytes) -> bool | None:
    """True=ok, False=rifiutato, None=non e' una risposta di binding."""
    if len(data) < 31 or data[:4] != HEADER or data[9] != BIND_REPLY_CODE:
        return None
    return {0xAA: True, 0x55: False}.get(data[10 + 17])


def _u16(p: bytes, i: int) -> int:
    return p[i] + 256 * p[i + 1]


def parse_frame(frame: bytes) -> dict | None:
    """Decodifica un frame di telemetria. None se non valido."""
    if len(frame) < FRAME_LEN or frame[:4] != HEADER:
        return None
    if frame[4] != 0x02 or frame[9] != 0x01:
        return None
    if checksum(frame[:138]) != frame[138]:
        return None
    p = frame[10:51]
    return {
        "mcu_temp": p[0] - 40,
        "motor_temp": p[1] - 40,
        "speed": p[2],
        "mcu_fault": p[3],
        "power": p[4] / 10,
        "battery_temp": p[5] - 40,
        "vcu_temp": p[6] - 40,
        "vehicle_temp": p[7] - 40,
        "bms_limit_discharge_current": _u16(p, 10) / 10,
        "bms_fault": p[13],
        "soc": p[14],
        "soh": p[15],
        "bms_limit_charge_current": _u16(p, 16) / 10,
        "battery_current": _u16(p, 18) / 10 - 300,
        "odometer": (p[20] + 256 * p[21] + 65536 * p[22]) / 10,
        "range": _u16(p, 23) / 10,
        "avg_consumption": p[26] / 10,
        "last20_consumption": p[25] / 10,
        "vcu_fault": p[30],
        "display_fault": p[31],
        "dcdc_fault": p[32],
        "obc_fault": p[33],
        "abs_fault": p[34],
    }


class FrameBuffer:
    """Ricompone frame spezzati su più notifiche BLE."""

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> list[dict]:
        self._buf += bytes(data)
        out: list[dict] = []
        while True:
            i = self._buf.find(HEADER)
            if i < 0:
                self._buf = self._buf[-3:]
                break
            self._buf = self._buf[i:]
            if len(self._buf) < FRAME_LEN:
                break
            parsed = parse_frame(self._buf[:FRAME_LEN])
            if parsed:
                out.append(parsed)
                self._buf = self._buf[FRAME_LEN:]
            else:
                self._buf = self._buf[1:]
        return out
