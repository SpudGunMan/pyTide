# pyTide

pyTide is a Pi-friendly tide clock built around XTide and pygame-ce for Ubuntu Linux on Pi like devices.

<img src="img/pytide.png" alt="pyTide screenshot" width="720" />

It is designed to:

- render a fullscreen or windowed tide clock
- read predictions from a local XTide installation
- update harmonics automatically from Flaterco or openwatersio sources


## Quick start

1. Run the automated install (app + XTide + initial harmonics):

   `sudo bash scripts/install.sh --user pi --install-dir /opt/pytide --with-xtide`

2. Enable autolaunch service:

   `sudo bash /opt/pytide/scripts/setup-autolaunch.sh --user pi --install-dir /opt/pytide`

3. Validate service status:

   `systemctl status pytide.service --no-pager`

4. Optional manual launch in windowed mode:

   `python -m app.main --windowed`

5. Optional manual launch in fullscreen kiosk mode:

   `python -m app.main --fullscreen`

For manual XTide install steps instead of scripts, see [Install XTide](#install-xtide-on-raspberry-pi-or-ubuntu).

## One-command install and autolaunch

For Raspberry Pi/Ubuntu deployments, use the helper scripts:

1. Install dependencies, deploy app to `/opt/pytide`, create virtualenv, and install Python packages:

   `sudo bash scripts/install.sh --user pi --install-dir /opt/pytide`

   To also install/build XTide and seed initial harmonics data in one pass:

   `sudo bash scripts/install.sh --user pi --install-dir /opt/pytide --with-xtide`

2. (Optional standalone) Install/build XTide and initial harmonics only:

   `sudo bash scripts/install-xtide.sh`

3. Install and enable systemd autolaunch service:

   `sudo bash /opt/pytide/scripts/setup-autolaunch.sh --user pi --install-dir /opt/pytide`

4. Validate service status:

   `systemctl status pytide.service --no-pager`

The install script creates `settings.json` from `settings.example.json` when missing, and preserves existing `settings.json` values across re-installs.

## Uninstall and rollback

To remove only the autolaunch service:

```bash
sudo bash /opt/pytide/scripts/uninstall.sh --service-name pytide --install-dir /opt/pytide
```

To remove both service and install directory:

```bash
sudo bash /opt/pytide/scripts/uninstall.sh --service-name pytide --install-dir /opt/pytide --purge
```


## CLI options

Run options are parsed in `app/config.py` via `TideClockConfig.from_args`.
CLI flags override any values loaded from `settings.example.json` and `settings.json`.

### Station and XTide

- `--station` (default: `LOCAL STATION`): XTide station name to render.
- `--xtide-path` (default: `/usr/local/bin/tide`): Path to the XTide `tide` executable.
- `--harmonics-dir` (default: `/usr/local/share/xtide`): Directory containing harmonics files.
- `--cache-dir` (default: `.pytide-cache`): Local cache directory.

### Coordinates and weather

- `--latitude` (default: `None`): Latitude for NOAA weather calls. Supports decimal or cardinal suffix (for example `48.4N`).
- `--longitude` (default: `None`): Longitude for NOAA weather calls. Supports decimal or cardinal suffix (for example `122.6W`).
- `--weather-refresh-seconds` (default: `14400`): Weather polling interval in seconds.
- `--disable-weather` (flag): Disable weather fetch entirely.

### Window and refresh behavior

- `--fullscreen` (flag): Launch in fullscreen mode.
- `--windowed` (flag): Launch in windowed mode.
- `--width` (default: `1280`): Window width in pixels.
- `--height` (default: `800`): Window height in pixels.
- `--refresh-seconds` (default: `300`): App refresh interval in seconds.
- `--harmonics-refresh-hours` (default: `336`): Harmonics refresh age threshold in hours.

### Theme and background

- `--theme` (default: `light`): Theme preset (`light` or `dark`).
- `--background-image` (default: `img/beach.jpeg`): Background image path.
- `--disable-background-image` (flag): Disable background image and use theme background color.
- `--background-overlay-alpha` (default: `88`): Global background shade alpha (`0-255`).

### Transparency controls

- `--panel-alpha` (default: `188`): Left forecast panel alpha (`0-255`).
- `--card-alpha` (default: `188`): Forecast card alpha (`0-255`).
- `--rail-alpha` (default: `212`): Right panel alpha (`0-255`).
- `--table-alpha` (default: `210`): Bottom table alpha (`0-255`).
- `--clock-face-alpha` (default: `140`): Clock-face tint alpha (`0-255`).

## Layout

- `app/config.py` - configuration defaults and data classes
- `app/harmonics_updater.py` - harmonics download and fallback logic
- `app/xtide.py` - XTide invocation and forecast parsing
- `app/render.py` - pygame-ce clock rendering
- `app/main.py` - app entry point and CLI
- `tests/test_xtide_parser.py` - parser smoke tests


### Mode notes

- If neither `--fullscreen` nor `--windowed` is provided, the app defaults to windowed mode.
- Alpha values are clamped to `0-255`.

## Install XTide on Raspberry Pi or Ubuntu

These are the minimal install steps for a Pi running Ubuntu Linux.

If you prefer automation, run:

```bash
sudo bash scripts/install-xtide.sh
```

Manual steps:

```bash
sudo apt-get update
sudo apt-get install -y build-essential libpng-dev wget xz-utils

cd /tmp
wget https://flaterco.com/files/xtide/libtcd-2.2.7-r3.tar.xz
tar xf libtcd-2.2.7-r3.tar.xz
cd libtcd-2.2.7
./configure
make
sudo make install
sudo ldconfig

cd /tmp
wget https://flaterco.com/files/xtide/xtide-2.16.tar.xz
tar xf xtide-2.16.tar.xz
cd xtide-2.16
./configure --without-x --disable-shared CPPFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib"
make
sudo make install

cd /tmp
rm -f harmonics-dwf-20251228-free.tar.xz*
wget https://flaterco.com/files/xtide/harmonics-dwf-20251228-free.tar.xz
tar xf harmonics-dwf-20251228-free.tar.xz
cd harmonics-dwf-20251228
sudo mkdir -p /usr/local/share/xtide
sudo cp harmonics-dwf-20251228-free.tcd /usr/local/share/xtide/

echo "/usr/local/share/xtide" | sudo tee /etc/xtide.conf

/usr/local/bin/tide -l "Palo Alto Yacht Harbor, San Francisco Bay, California"
```

If your location is outside the US, use a harmonics file from the `openwatersio/tide-database` releases instead of the Flaterco bundle.

## Set the tide station location and weather coordinates

XTide needs a specific station name; the clock will not work correctly until the configured station matches a real entry in your harmonics file.

```bash
python -m app.main --station "La Conner, Washington" 
```

List the available stations:

```bash
/usr/local/bin/tide -m l
```

Then choose a station and set it in the app configuration. The simplest approach is to pass it on the command line:

```bash
python -m app.main --station "Nummy Island, Grassy Sound Channel, Hereford Inlet, New Jersey"
```

Or copy example config `settings.example.json` to `settings.json`:

```json
{
  "station": "Nummy Island, Grassy Sound Channel, Hereford Inlet, New Jersey"
}
```

Keep the station name exactly as listed by XTide, including commas and punctuation.


## Automatic harmonics updates

The app keeps a local copy of the harmonics file and refreshes it when it is older than the configured age window (default: 336 hours / 14 days).

```python
from app.harmonics_updater import refresh_harmonics_if_needed

path = refresh_harmonics_if_needed("/usr/local/share/xtide", max_age_hours=336)
print(path)
```
This uses the Flaterco archive by default and falls back to the last known good `.tcd` file if the network download fails.
