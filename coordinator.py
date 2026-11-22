"""Coordinator: si connette via BLE, chiede i dati e si disconnette."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from bleak import BleakClient
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RESPONSE_TIMEOUT, SCAN_INTERVAL_SECONDS
from .protocol import CMD_VEHICLE_INFO, FrameBuffer, build_bind, build_command, parse_bind_reply

_LOGGER = logging.getLogger(__name__)
FAIL_INTERVAL = 300  # secondi tra le letture quando lo scooter non risponde (evita di tenere occupato l'adattatore)
STALE_MAX = 600  # secondi: oltre, i sensori diventano "non disponibili"
_NERVA_SERVICE_UUID = "fff0"
_NERVA_NOTIFY_UUID = "fff1"
_NERVA_WRITE_UUID = "fff2"


def _matches_uuid16(uuid: str, short_uuid: str) -> bool:
    """Confronta un UUID Bluetooth a 16 bit nelle forme Bleak più comuni."""
    normalized = str(uuid).lower()
    return normalized in {
        short_uuid,
        f"0000{short_uuid}",
        f"0000{short_uuid}-0000-1000-8000-00805f9b34fb",
    }


def _find_chars(client: BleakClient):
    """Trova esclusivamente FFF1/FFF2 nel servizio Nerva FFF0."""
    services = list(client.services)
    for idx, svc in enumerate(services):
        service_uuid = str(svc.uuid).lower()
        _LOGGER.debug("Servizio %s: %s", idx, service_uuid)
        for ch in svc.characteristics:
            _LOGGER.debug("  %s %s", ch.uuid, ch.properties)

        if not _matches_uuid16(service_uuid, _NERVA_SERVICE_UUID):
            continue

        notify = next(
            (
                char
                for char in svc.characteristics
                if _matches_uuid16(char.uuid, _NERVA_NOTIFY_UUID)
                and ("notify" in char.properties or "indicate" in char.properties)
            ),
            None,
        )
        write = next(
            (
                char
                for char in svc.characteristics
                if _matches_uuid16(char.uuid, _NERVA_WRITE_UUID)
                and (
                    "write-without-response" in char.properties
                    or "write" in char.properties
                )
            ),
            None,
        )
        if notify is not None and write is not None:
            _LOGGER.debug(
                "Uso caratteristiche BLE notify=%s, write=%s",
                notify.uuid,
                write.uuid,
            )
            return notify, write
    raise UpdateFailed(
        "Servizio BLE Nerva 0000fff0 con notify FFF1 e write FFF2 non trovato"
    )


class NervaCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, address: str, vin: str, model: str, password: str = "") -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.address, self.vin, self.model, self.password = address, vin, model, password
        self.connected: bool = False
        self._last_ok: float = 0.0
        self._lock = asyncio.Lock()

    def _fallback_or_raise(self, msg: str, err: Exception | None = None) -> dict:
        self.connected = False
        self.update_interval = timedelta(seconds=FAIL_INTERVAL)
        if self.data and time.monotonic() - self._last_ok < STALE_MAX:
            _LOGGER.debug("%s - mantengo ultimi dati validi", msg)
            return self.data
        if err:
            raise UpdateFailed(msg) from err
        raise UpdateFailed(msg)

    async def _async_update_data(self) -> dict:
        # una sola connessione alla volta: due letture in parallelo si bloccano a vicenda (BlueZ "InProgress")
        if self._lock.locked():
            _LOGGER.debug("Lettura già in corso, salto questo giro")
            if self.data:
                return self.data
            raise UpdateFailed("Lettura già in corso")
        async with self._lock:
            return await self._read_scooter()

    async def _read_scooter(self) -> dict:
        # se lo scooter non sta trasmettendo (spento/fuori portata) non occupo l'adattatore con tentativi inutili
        if not bluetooth.async_address_present(self.hass, self.address, connectable=True):
            return self._fallback_or_raise("Scooter non visibile via Bluetooth (spento o fuori portata)")
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            return self._fallback_or_raise("Scooter non raggiungibile via Bluetooth (spento o fuori portata)")
        buf = FrameBuffer()
        got: asyncio.Future = self.hass.loop.create_future()
        bind_done = asyncio.Event()

        def _on_data(_, data: bytearray) -> None:
            _LOGGER.debug("Notifica BLE: %s", bytes(data).hex())
            bound = parse_bind_reply(bytes(data))
            if bound is not None:
                _LOGGER.debug("Risposta binding: %s", "ok" if bound else "RIFIUTATO (password errata?)")
                bind_done.set()
            for frame in buf.feed(bytes(data)):
                if not got.done():
                    got.set_result(frame)

        try:
            # niente wait_for esterno: annullare una connect a metà lascia BlueZ in "InProgress".
            # un solo tentativo per giro: con segnale debole ogni tentativo può durare ~20 s e tiene occupato hci0;
            # si riprova al giro successivo
            client = await establish_connection(
                BleakClientWithServiceCache, device, self.address, max_attempts=1
            )
        except Exception as err:  # noqa: BLE001
            return self._fallback_or_raise(f"Connessione BLE fallita: {err!r}", err)
        try:
            if not client.is_connected:
                raise UpdateFailed("La connessione BLE si è interrotta prima dell'attivazione delle notifiche")
            notify, write = _find_chars(client)
            use_response = "write-without-response" not in write.properties
            await client.start_notify(notify, _on_data)
            await asyncio.sleep(0.3)  # lascia al dispositivo il tempo di attivare le notifiche
            if self.password:
                await client.write_gatt_char(write, build_bind(self.vin, self.password, self.model), response=use_response)
                try:
                    await asyncio.wait_for(bind_done.wait(), 3)
                except asyncio.TimeoutError:
                    _LOGGER.debug("Nessuna risposta al binding, continuo comunque")
            cmd = build_command(CMD_VEHICLE_INFO, self.vin, self.model)
            await client.write_gatt_char(write, cmd, response=use_response)
            data = await asyncio.wait_for(got, RESPONSE_TIMEOUT)
            self.connected = True
            self._last_ok = time.monotonic()
            self.update_interval = timedelta(seconds=SCAN_INTERVAL_SECONDS)
            return data
        except asyncio.TimeoutError as err:
            return self._fallback_or_raise("Nessuna notifica telemetrica ricevuta dallo scooter entro il timeout", err)
        except UpdateFailed as err:
            return self._fallback_or_raise(str(err), err)
        except Exception as err:
            return self._fallback_or_raise(f"Errore lettura BLE: {err}", err)
        finally:
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:  # noqa: BLE001
                pass