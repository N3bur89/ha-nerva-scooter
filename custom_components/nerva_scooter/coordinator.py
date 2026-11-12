"""Coordinator: si connette via BLE, chiede i dati e si disconnette."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from bleak import BleakClient
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RESPONSE_TIMEOUT, SCAN_INTERVAL_SECONDS
from .protocol import CMD_VEHICLE_INFO, FrameBuffer, build_bind, build_command, parse_bind_reply

_LOGGER = logging.getLogger(__name__)
_STANDARD = ("00001800", "00001801", "0000180a")


def _find_chars(client: BleakClient):
    """Cerca (caratteristica notify, caratteristica write) nel servizio dati."""
    services = list(client.services)
    for idx, svc in enumerate(services):
        _LOGGER.debug("Servizio %s: %s", idx, svc.uuid)
        for ch in svc.characteristics:
            _LOGGER.debug("  %s %s", ch.uuid, ch.properties)

    # Priorità al servizio seriale standard 0000fff0, poi agli altri non standard
    fff0 = [s for s in services if s.uuid.startswith("0000fff0")]
    others = [s for s in services if not s.uuid.startswith(_STANDARD) and not s.uuid.startswith("0000fff0")]
    for svc in fff0 + others:
        notify = [c for c in svc.characteristics if "notify" in c.properties or "indicate" in c.properties]
        write = [c for c in svc.characteristics if "write-without-response" in c.properties or "write" in c.properties]
        if notify and write:
            return notify[0], write[0]
    raise UpdateFailed("Caratteristiche BLE notify/write non trovate")


class NervaCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, address: str, vin: str, model: str, password: str = "") -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.address, self.vin, self.model, self.password = address, vin, model, password

    async def _async_update_data(self) -> dict:
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            raise UpdateFailed("Scooter non raggiungibile via Bluetooth (spento o fuori portata)")
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
            client = await establish_connection(BleakClientWithServiceCache, device, self.address)
        except Exception as err:
            raise UpdateFailed(f"Connessione BLE fallita: {err}") from err
        try:
            notify, write = _find_chars(client)
            use_response = "write-without-response" not in write.properties
            await client.start_notify(notify, _on_data)
            if self.password:
                await client.write_gatt_char(write, build_bind(self.vin, self.password, self.model), response=use_response)
                try:
                    await asyncio.wait_for(bind_done.wait(), 3)
                except asyncio.TimeoutError:
                    _LOGGER.debug("Nessuna risposta al binding, continuo comunque")
            cmd = build_command(CMD_VEHICLE_INFO, self.vin, self.model)
            await client.write_gatt_char(write, cmd, response=use_response)
            return await asyncio.wait_for(got, RESPONSE_TIMEOUT)
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Nessuna risposta dallo scooter (codice modello errato?)") from err
        finally:
            try:
                await client.disconnect()  # libera la connessione per l'app Nerva
            except Exception:  # noqa: BLE001
                pass
