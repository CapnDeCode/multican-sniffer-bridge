from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class PlotPoint:
    time_min: float
    can_id: int
    byte_index: int
    value: int


@dataclass
class ScaledPoint:
    time_min: float
    label: str
    value: float


@dataclass
class ScaleSpec:
    label: str
    can_id: int
    byte_index: int
    scale: float
    offset: float


def parse_can_id(value: str) -> int:
    value = value.strip().lower()
    if value.startswith("0x"):
        return int(value, 16)
    return int(value, 16) if all(c in "0123456789abcdef" for c in value) else int(value, 10)


def parse_byte_indexes(value: str) -> list[int]:
    indexes: list[int] = []
    for part in value.split(","):
        p = part.strip()
        if not p:
            continue
        idx = int(p, 10)
        if idx < 0 or idx > 7:
            raise ValueError(f"byte index must be in [0, 7], got {idx}")
        indexes.append(idx)
    if not indexes:
        raise ValueError("at least one byte index is required")
    return sorted(set(indexes))


def parse_can_ids(value: str) -> list[int]:
    ids: list[int] = []
    for part in value.split(","):
        p = part.strip()
        if not p:
            continue
        ids.append(parse_can_id(p))
    if not ids:
        raise ValueError("at least one CAN ID is required")
    return sorted(set(ids))


def parse_scale_specs(values: list[str]) -> list[ScaleSpec]:
    """
    Parse repeated --series options with format:
    label:can_id:byte_index:scale:offset
    Example:
      SOC[%]:0x70A:0:1:0
      Vpack[V]:0x70A:1:0.4:0
      Ichg[A]:0x70A:3:0.0368:0
    """
    specs: list[ScaleSpec] = []
    for value in values:
        parts = [p.strip() for p in value.split(":")]
        if len(parts) != 5:
            raise ValueError(
                "series spec must be 'label:can_id:byte_index:scale:offset', "
                f"got: {value}"
            )
        label, can_id_raw, byte_raw, scale_raw, offset_raw = parts
        if not label:
            raise ValueError(f"series label cannot be empty: {value}")
        can_id = parse_can_id(can_id_raw)
        byte_index = int(byte_raw, 10)
        if byte_index < 0 or byte_index > 7:
            raise ValueError(f"series byte index must be in [0, 7], got {byte_index}")
        scale = float(scale_raw)
        offset = float(offset_raw)
        specs.append(
            ScaleSpec(
                label=label,
                can_id=can_id,
                byte_index=byte_index,
                scale=scale,
                offset=offset,
            )
        )
    if not specs:
        raise ValueError("at least one --series specification is required")
    return specs


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _extract_points(
    rows: Iterable[dict],
    *,
    ids: set[int],
    byte_indexes: list[int],
    start_time: Optional[float],
    end_time: Optional[float],
    relative_time: bool,
) -> list[PlotPoint]:
    points: list[PlotPoint] = []
    first_ts: Optional[float] = None

    for row in rows:
        can_id = int(row["can_id"])
        if can_id not in ids:
            continue

        ts = float(row["timestamp"])
        if start_time is not None and ts < start_time:
            continue
        if end_time is not None and ts > end_time:
            continue

        data_hex = str(row.get("data_hex", ""))
        data = bytes.fromhex(data_hex) if data_hex else b""

        if first_ts is None:
            first_ts = ts
        x_seconds = ts - first_ts if relative_time else ts
        x_minutes = x_seconds / 60.0

        for byte_idx in byte_indexes:
            if byte_idx >= len(data):
                continue
            points.append(
                PlotPoint(
                    time_min=x_minutes,
                    can_id=can_id,
                    byte_index=byte_idx,
                    value=data[byte_idx],
                )
            )

    return points


def create_plot(
    *,
    input_path: Path,
    can_ids: list[int],
    byte_indexes: list[int],
    output_path: Path,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    relative_time: bool = True,
    show: bool = False,
) -> int:
    if "MPLCONFIGDIR" not in os.environ:
        mpl_dir = Path(tempfile.gettempdir()) / "sniffer-mpl"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(mpl_dir)

    import matplotlib.pyplot as plt

    rows = _load_jsonl(input_path)
    points = _extract_points(
        rows,
        ids=set(can_ids),
        byte_indexes=byte_indexes,
        start_time=start_time,
        end_time=end_time,
        relative_time=relative_time,
    )

    if not points:
        return 0

    fig, ax = plt.subplots(figsize=(12, 6))

    for can_id in sorted(set(p.can_id for p in points)):
        for byte_idx in byte_indexes:
            series = [p for p in points if p.can_id == can_id and p.byte_index == byte_idx]
            if not series:
                continue
            xs = [p.time_min for p in series]
            ys = [p.value for p in series]
            ax.plot(xs, ys, linewidth=1.0, label=f"0x{can_id:03X}[{byte_idx}]")

    ax.set_xlabel("Time (min from first sample)" if relative_time else "Timestamp (epoch min)")
    ax.set_ylabel("Byte value (0-255)")
    ax.set_ylim(bottom=0)
    ax.set_title("CAN byte trends over time")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return len(points)


def _extract_scaled_points(
    rows: Iterable[dict],
    *,
    specs: list[ScaleSpec],
    start_time: Optional[float],
    end_time: Optional[float],
    relative_time: bool,
) -> list[ScaledPoint]:
    points: list[ScaledPoint] = []
    first_ts: Optional[float] = None
    ids = {s.can_id for s in specs}
    by_id: dict[int, list[ScaleSpec]] = {}
    for spec in specs:
        by_id.setdefault(spec.can_id, []).append(spec)

    for row in rows:
        can_id = int(row["can_id"])
        if can_id not in ids:
            continue

        ts = float(row["timestamp"])
        if start_time is not None and ts < start_time:
            continue
        if end_time is not None and ts > end_time:
            continue

        data_hex = str(row.get("data_hex", ""))
        if not data_hex:
            continue
        data = bytes.fromhex(data_hex)

        if first_ts is None:
            first_ts = ts

        x_seconds = ts - first_ts if relative_time else ts
        x_minutes = x_seconds / 60.0

        for spec in by_id.get(can_id, []):
            if spec.byte_index >= len(data):
                continue
            raw_value = float(data[spec.byte_index])
            scaled = (raw_value * spec.scale) + spec.offset
            points.append(
                ScaledPoint(
                    time_min=x_minutes,
                    label=spec.label,
                    value=scaled,
                )
            )

    return points


def create_scaled_plot(
    *,
    input_path: Path,
    specs: list[ScaleSpec],
    output_path: Path,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    relative_time: bool = True,
    show: bool = False,
) -> int:
    if "MPLCONFIGDIR" not in os.environ:
        mpl_dir = Path(tempfile.gettempdir()) / "sniffer-mpl"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(mpl_dir)

    import matplotlib.pyplot as plt

    rows = _load_jsonl(input_path)
    points = _extract_scaled_points(
        rows,
        specs=specs,
        start_time=start_time,
        end_time=end_time,
        relative_time=relative_time,
    )
    if not points:
        return 0

    fig, ax = plt.subplots(figsize=(12, 6))
    labels = sorted(set(p.label for p in points))
    for label in labels:
        series = [p for p in points if p.label == label]
        xs = [p.time_min for p in series]
        ys = [p.value for p in series]
        ax.plot(xs, ys, label=label, linewidth=1.2)

    ax.set_xlabel("Time (min from first sample)" if relative_time else "Timestamp (epoch min)")
    ax.set_ylabel("Scaled value")
    ax.set_ylim(bottom=0)
    ax.set_title("Configured scaled channels")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return len(points)

