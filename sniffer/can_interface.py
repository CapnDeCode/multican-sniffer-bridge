from __future__ import annotations

from dataclasses import dataclass

import can


DEFAULT_BUSTYPE = "seeedstudio"


def open_bus(device: str, bitrate: int) -> can.Bus:
    """
    Open a python-can Bus for a USB-CAN Analyzer compatible with the
    Seeed Studio serial protocol.
    """
    return can.interface.Bus(
        bustype=DEFAULT_BUSTYPE,
        channel=device,
        bitrate=bitrate,
        receive_own_messages=False,
    )


@dataclass
class CanChannel:
    name: str  # e.g. "battery" or "charger"
    bus: can.Bus

