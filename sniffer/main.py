from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from .can_interface import CanChannel, open_bus
from .config import CanConfig, LoggingConfig, OutputMode
from .logging_output import create_output_writer
from .plot_service import (
    create_plot,
    create_scaled_plot,
    parse_byte_indexes,
    parse_can_ids,
    parse_scale_specs,
)
from .router import run_router, run_sniffer

app = typer.Typer(add_completion=False)


@app.command()
def run(
    channels: int = typer.Option(
        1,
        "--channels",
        "-c",
        help="Number of CAN channels to use (1=sniffer, 2=router).",
    ),
    device_a: str = typer.Option(
        ...,
        "--device-a",
        help="Serial device for adapter A (e.g. /dev/tty.usbserial-A).",
    ),
    device_b: Optional[str] = typer.Option(
        None,
        "--device-b",
        help="Serial device for adapter B (required when --channels 2).",
    ),
    bitrate: int = typer.Option(
        250000,
        "--bitrate",
        help="CAN bitrate (default: 250000).",
    ),
    output: OutputMode = typer.Option(
        OutputMode.CONSOLE,
        "--output",
        "-o",
        case_sensitive=False,
        help="Output mode: csv, jsonl, console.",
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output-path",
        help="Output file path for CSV/JSONL modes.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging.",
    ),
) -> None:
    """
    Run CAN sniffer/router in 1- or 2-channel mode.
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    can_cfg = CanConfig(
        channels=channels,
        device_a=device_a,
        device_b=device_b,
        bitrate=bitrate,
    )
    log_cfg = LoggingConfig(
        output_mode=output,
        output_path=output_path,
        debug=debug,
    )

    try:
        can_cfg.validate()
        log_cfg.validate()
    except ValueError as exc:
        logging.error(str(exc))
        raise typer.Exit(code=1) from exc

    writer = create_output_writer(log_cfg.output_mode, log_cfg.output_path)

    try:
        bus_a = open_bus(can_cfg.device_a, can_cfg.bitrate)
        channel_a = CanChannel(name="A", bus=bus_a)

        if can_cfg.channels == 1:
            logging.info("Starting 1-channel sniffer on %s", can_cfg.device_a)
            run_sniffer(channel_a, writer)
        else:
            assert can_cfg.device_b is not None
            bus_b = open_bus(can_cfg.device_b, can_cfg.bitrate)
            channel_b = CanChannel(name="B", bus=bus_b)

            logging.info(
                "Starting 2-channel router: %s <-> %s",
                can_cfg.device_a,
                can_cfg.device_b,
            )
            run_router(channel_a, channel_b, writer)
    except KeyboardInterrupt:
        logging.info("Interrupted, shutting down...")
    finally:
        try:
            writer.close()
        except Exception:  # pragma: no cover - best-effort close
            pass


@app.command()
def plot(
    input_path: Path = typer.Option(
        ...,
        "--input-path",
        help="Path to JSONL capture file.",
    ),
    can_ids: str = typer.Option(
        "0x70A,0x718",
        "--can-ids",
        help="Comma-separated CAN IDs to plot, e.g. 0x70A,0x718.",
    ),
    byte_indexes: str = typer.Option(
        "1,2,3,4,5,6",
        "--byte-indexes",
        help="Comma-separated byte indexes to plot (0..7).",
    ),
    output_path: Path = typer.Option(
        Path("can_plot.png"),
        "--output-path",
        help="Output PNG path for the generated plot.",
    ),
    start_time: Optional[float] = typer.Option(
        None,
        "--start-time",
        help="Optional start epoch timestamp filter.",
    ),
    end_time: Optional[float] = typer.Option(
        None,
        "--end-time",
        help="Optional end epoch timestamp filter.",
    ),
    absolute_time: bool = typer.Option(
        False,
        "--absolute-time",
        help="Use absolute timestamps on X axis instead of relative seconds.",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        help="Show interactive plot window in addition to saving PNG.",
    ),
) -> None:
    """
    Plot CAN payload byte trends from a JSONL capture file.
    """
    if not input_path.exists():
        logging.error("Input file does not exist: %s", input_path)
        raise typer.Exit(code=1)

    try:
        ids = parse_can_ids(can_ids)
        indexes = parse_byte_indexes(byte_indexes)
    except ValueError as exc:
        logging.error(str(exc))
        raise typer.Exit(code=1) from exc

    point_count = create_plot(
        input_path=input_path,
        can_ids=ids,
        byte_indexes=indexes,
        output_path=output_path,
        start_time=start_time,
        end_time=end_time,
        relative_time=not absolute_time,
        show=show,
    )

    if point_count == 0:
        logging.warning("No matching points found for the selected filters.")
        raise typer.Exit(code=2)

    logging.info("Saved plot with %s points to %s", point_count, output_path)


@app.command("plot-scaled")
def plot_scaled(
    input_path: Path = typer.Option(
        ...,
        "--input-path",
        help="Path to JSONL capture file.",
    ),
    series: list[str] = typer.Option(
        ...,
        "--series",
        help=(
            "Repeatable series spec: label:can_id:byte_index:scale:offset "
            "(example: 'SOC[%]:0x70A:0:1:0')"
        ),
    ),
    output_path: Path = typer.Option(
        Path("can_scaled_plot.png"),
        "--output-path",
        help="Output PNG path for the generated scaled plot.",
    ),
    start_time: Optional[float] = typer.Option(
        None,
        "--start-time",
        help="Optional start epoch timestamp filter.",
    ),
    end_time: Optional[float] = typer.Option(
        None,
        "--end-time",
        help="Optional end epoch timestamp filter.",
    ),
    absolute_time: bool = typer.Option(
        False,
        "--absolute-time",
        help="Use absolute timestamps on X axis instead of relative seconds.",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        help="Show interactive plot window in addition to saving PNG.",
    ),
) -> None:
    """
    Plot configured scaled channels in one chart.
    """
    if not input_path.exists():
        logging.error("Input file does not exist: %s", input_path)
        raise typer.Exit(code=1)

    try:
        specs = parse_scale_specs(series)
    except ValueError as exc:
        logging.error(str(exc))
        raise typer.Exit(code=1) from exc

    point_count = create_scaled_plot(
        input_path=input_path,
        specs=specs,
        output_path=output_path,
        start_time=start_time,
        end_time=end_time,
        relative_time=not absolute_time,
        show=show,
    )

    if point_count == 0:
        logging.warning("No matching points found for scaled plot.")
        raise typer.Exit(code=2)

    logging.info("Saved scaled plot with %s points to %s", point_count, output_path)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

