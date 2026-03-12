## sniffer

Python-based CAN sniffer/router using inexpensive USB–CAN adapters.

### Features

- 1-channel mode: passive sniffer that listens on a single CAN bus and logs frames.
- 2-channel mode: bi-directional router between two CAN segments (A⇄B) with direction/origin tagging.
- Selectable output:
  - CSV file
  - JSON Lines (JSONL) file
  - Console-only debug logging

### Environment

This project is intended to be managed with `uv` and a `pyproject.toml` file.

### Getting Started (uv)

If you are starting from scratch with a new folder:

```bash
mkdir sniffer
cd sniffer
uv init
```

For this existing project, from repository root:

```bash
uv sync
```

Run sniffer (1 channel):

```bash
uv run sniffer run \
  --channels 1 \
  --device-a /dev/tty.usbserial-1310 \
  --output console
```

Run router (2 channels):

```bash
uv run sniffer run \
  --channels 2 \
  --device-a /dev/tty.usbserial-A \
  --device-b /dev/tty.usbserial-B \
  --output jsonl \
  --output-path capture.jsonl
```

Find serial devices on macOS:

```bash
ls /dev/tty.*
```

### Plotting from a capture

Generate a PNG chart from a JSONL capture to visualize byte trends over time:

```bash
uv run sniffer plot \
  --input-path full_charge_cycle.jsonl \
  --can-ids 0x70A,0x718 \
  --byte-indexes 1,2,3,4,5,6 \
  --output-path charge_trends.png
```

Generate a combined scaled plot (proposed SOC/Voltage/Current channels):

```bash
uv run sniffer plot-scaled \
  --input-path full_charge_cycle.jsonl \
  --series "SOC[%]:0x70A:0:1:0" \
  --series "Vpack[V]:0x70A:1:0.4:0" \
  --series "Ichg[A]:0x70A:3:0.0368:0" \
  --output-path scaled_channels.png
```

