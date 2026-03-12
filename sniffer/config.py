from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class AppMode(Enum):
    SNIFFER_1CH = auto()
    ROUTER_2CH = auto()


class OutputMode(str, Enum):
    CSV = "csv"
    JSONL = "jsonl"
    CONSOLE = "console"


@dataclass
class CanConfig:
    channels: int
    device_a: str
    bitrate: int = 250_000
    device_b: Optional[str] = None

    def validate(self) -> None:
        if self.channels not in (1, 2):
            raise ValueError(f"channels must be 1 or 2, got {self.channels}")

        if not self.device_a:
            raise ValueError("device_a must be provided")

        if self.channels == 2 and not self.device_b:
            raise ValueError("device_b must be provided when channels == 2")


@dataclass
class LoggingConfig:
    output_mode: OutputMode
    output_path: Optional[Path] = None
    debug: bool = False

    def validate(self) -> None:
        if self.output_mode in (OutputMode.CSV, OutputMode.JSONL):
            if self.output_path is None:
                raise ValueError("output_path must be provided for file outputs")
        else:
            # console mode: ignore output_path
            self.output_path = None

