from __future__ import annotations

import time
from typing import Optional

import can

from .can_interface import CanChannel
from .logging_output import BaseOutputWriter, create_frame_record


def _handle_message(
    *,
    msg: can.Message,
    origin_channel: CanChannel,
    dest_channel: Optional[CanChannel],
    writer: BaseOutputWriter,
) -> None:
    # Skip frames that are marked as transmitted by this host to reduce loops
    if getattr(msg, "is_tx", False):
        return

    record = create_frame_record(
        origin=origin_channel.name,
        can_id=msg.arbitration_id,
        dlc=msg.dlc,
        data=bytes(msg.data),
        timestamp=msg.timestamp if hasattr(msg, "timestamp") else time.time(),
    )
    writer.write_frame(record)

    if dest_channel is not None:
        try:
            dest_channel.bus.send(msg)
        except can.CanError:
            # For now we just ignore send errors; could be extended with logging/stats
            pass


def run_sniffer(channel: CanChannel, writer: BaseOutputWriter, poll_timeout: float = 0.001) -> None:
    """
    Single-channel sniffer loop. Reads frames from one CAN channel and logs them.
    """
    while True:
        msg = channel.bus.recv(timeout=poll_timeout)
        if msg is None:
            continue
        _handle_message(
            msg=msg,
            origin_channel=channel,
            dest_channel=None,
            writer=writer,
        )


def run_router(
    channel_a: CanChannel,
    channel_b: CanChannel,
    writer: BaseOutputWriter,
    poll_timeout: float = 0.001,
) -> None:
    """
    Bi-directional router between two CAN segments with logging (e.g. battery <-> charger).
    """
    bus_a = channel_a.bus
    bus_b = channel_b.bus

    while True:
        msg_a = bus_a.recv(timeout=poll_timeout)
        if msg_a is not None:
            _handle_message(
                msg=msg_a,
                origin_channel=channel_a,
                dest_channel=channel_b,
                writer=writer,
            )

        msg_b = bus_b.recv(timeout=poll_timeout)
        if msg_b is not None:
            _handle_message(
                msg=msg_b,
                origin_channel=channel_b,
                dest_channel=channel_a,
                writer=writer,
            )

