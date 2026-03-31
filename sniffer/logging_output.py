from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Optional

from .config import OutputMode


@dataclass
class FrameRecord:
    timestamp: float
    iso_timestamp: str
    origin: Optional[str]
    can_id: int
    dlc: int
    data_hex: str          # compact hex, e.g. "4254590000000000"
    data_hex_spaced: str   # spaced hex, e.g. "42 54 59 00 00 00 00 00"
    data_ascii: str        # printable ASCII, non-printables as '.'


class BaseOutputWriter:
    def write_frame(self, record: FrameRecord) -> None:  # pragma: no cover - IO wrapper
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - IO wrapper
        pass


class MultiOutputWriter(BaseOutputWriter):
    def __init__(self, writers: list[BaseOutputWriter]) -> None:
        self._writers = writers

    def write_frame(self, record: FrameRecord) -> None:
        for writer in self._writers:
            writer.write_frame(record)

    def close(self) -> None:
        for writer in self._writers:
            writer.close()


class CsvOutputWriter(BaseOutputWriter):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh: IO[str] = path.open("w", newline="")
        self._writer = csv.DictWriter(
            self._fh,
            fieldnames=[
                "timestamp",
                "origin",
                "can_id",
                "dlc",
                "data_hex",
            ],
        )
        self._writer.writeheader()

    def write_frame(self, record: FrameRecord) -> None:
        self._writer.writerow(
            {
                "timestamp": record.timestamp,
                "origin": record.origin or "",
                "can_id": record.can_id,
                "dlc": record.dlc,
                "data_hex": record.data_hex,
            }
        )

    def close(self) -> None:
        self._fh.close()


class JsonlOutputWriter(BaseOutputWriter):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh: IO[str] = path.open("w", encoding="utf-8")

    def write_frame(self, record: FrameRecord) -> None:
        payload = {
            "timestamp": record.timestamp,
            "origin": record.origin,
            "can_id": record.can_id,
            "dlc": record.dlc,
            "data_hex": record.data_hex,
        }
        self._fh.write(json.dumps(payload, separators=(",", ":")) + "\n")

    def close(self) -> None:
        self._fh.close()


class ConsoleOutputWriter(BaseOutputWriter):
    def __init__(self, stream: Optional[IO[str]] = None) -> None:
        self._stream = stream or sys.stdout

    def write_frame(self, record: FrameRecord) -> None:
        prefix = f"{record.iso_timestamp} "
        if record.origin:
            prefix += f"origin={record.origin} "
        line = (
            f"{prefix}id=0x{record.can_id:03X} dlc={record.dlc} "
            f"data_hex_spaced=\"{record.data_hex_spaced}\" "
            f"ascii=\"{record.data_ascii}\""
        )
        print(line, file=self._stream)


def create_frame_record(
    *,
    origin: Optional[str],
    can_id: int,
    dlc: int,
    data: bytes,
    timestamp: Optional[float] = None,
) -> FrameRecord:
    ts = timestamp if timestamp is not None else datetime.now().timestamp()
    iso = datetime.fromtimestamp(ts).isoformat()
    data_hex = data.hex()
    data_hex_spaced = " ".join(f"{b:02X}" for b in data)
    data_ascii = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return FrameRecord(
        timestamp=ts,
        iso_timestamp=iso,
        origin=origin,
        can_id=can_id,
        dlc=dlc,
        data_hex=data_hex,
        data_hex_spaced=data_hex_spaced,
        data_ascii=data_ascii,
    )


def create_output_writer(output_mode: OutputMode, path: Optional[Path]) -> BaseOutputWriter:
    if output_mode == OutputMode.CSV:
        if path is None:
            raise ValueError("CSV output requires a file path")
        return MultiOutputWriter([CsvOutputWriter(path), ConsoleOutputWriter()])
    if output_mode == OutputMode.JSONL:
        if path is None:
            raise ValueError("JSONL output requires a file path")
        return MultiOutputWriter([JsonlOutputWriter(path), ConsoleOutputWriter()])
    return ConsoleOutputWriter()

