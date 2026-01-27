# Blesk

[![Tests](https://github.com/smarthall/blesk/actions/workflows/test.yml/badge.svg)](https://github.com/smarthall/blesk/actions/workflows/test.yml)
[![Code Quality](https://github.com/smarthall/blesk/actions/workflows/lint.yml/badge.svg)](https://github.com/smarthall/blesk/actions/workflows/lint.yml)

A Python command-line tool for controlling Desky standing desks via Bluetooth Low Energy (BLE). Blesk provides a simple interface to adjust desk height, save and recall presets, and manage multiple desk configurations.

## Features

- **Height Control**: Move your desk to any specific height in millimeters
- **Preset Management**: Save and recall up to 4 preset heights
- **Multi-desk Support**: Configure and manage multiple desks using profiles
- **Auto-discovery**: Automatically detect nearby Desky desks
- **Cross-platform**: Works on any platform with BLE support (Linux, macOS, Windows)
- **Async Architecture**: Built on modern async Python for efficient operation

## Requirements

- Python 3.13 or later
- Bluetooth Low Energy (BLE) adapter
- Desky standing desk with Bluetooth support

## Installation

### Using pipx (Recommended)

```bash
pipx install blesk
```

### Using pip

```bash
pip install blesk
```

### From Source

```bash
git clone https://github.com/danhall/blesk.git
cd blesk
poetry install
poetry run blesk --help
```

## Quick Start

1. **Discover available desks:**
   ```bash
   blesk list desks
   ```

2. **Configure your desk:**
   ```bash
   blesk set desk <ADDRESS>
   ```
   Replace `<ADDRESS>` with your desk's Bluetooth address from the discovery output.

3. **Move to a specific height:**
   ```bash
   blesk go height 1000
   ```
   This moves the desk to 1000mm (100cm).

4. **Check current height:**
   ```bash
   blesk get current
   ```

## Usage

### Basic Commands

#### List Available Desks
```bash
blesk list desks
```
Scans for nearby Desky desks and displays their Bluetooth addresses and names.

#### Configure a Desk
```bash
blesk set desk <ADDRESS>
```
Sets the default desk to use for commands. The address is saved in your config file.

#### Move to Height
```bash
blesk go height <MILLIMETERS>
```
Moves the desk to the specified height in millimeters.

Example:
```bash
blesk go height 750   # Sitting height (75cm)
blesk go height 1150  # Standing height (115cm)
```

#### Use Presets
```bash
blesk go preset <1-4>
```
Moves the desk to one of the saved presets (1-4).

#### Get Current Height
```bash
blesk get current
```
Displays the current desk height in millimeters.

#### Get Preset Heights
```bash
blesk get preset all        # Get all preset heights
blesk get preset <1-4>      # Get a specific preset
```

### Advanced Options

#### Profiles
Manage multiple desks using different profiles:
```bash
blesk --profile home go height 1000
blesk --profile office go height 1000
```

#### Custom Config File
Specify a custom configuration file:
```bash
blesk --config /path/to/config.ini set desk <ADDRESS>
```

#### Debug Output
Enable debug or verbose logging:
```bash
blesk --debug get current
blesk --verbose go height 1000
```

## Configuration

Configuration is stored in a platform-specific directory:
- Linux: `~/.config/blesk/config.ini`
- macOS: `~/Library/Application Support/blesk/config.ini`
- Windows: `%LOCALAPPDATA%\blesk\config.ini`

Example config file:
```ini
[default]
address = AA:BB:CC:DD:EE:FF

[home]
address = 11:22:33:44:55:66

[office]
address = 77:88:99:AA:BB:CC
```

## Development

### Setup

Clone the repository and install dependencies:
```bash
git clone https://github.com/danhall/blesk.git
cd blesk
poetry install
```

### Running Tests

```bash
poetry run pytest
```

With coverage:
```bash
poetry run pytest --cov=blesk
```

### Code Quality

This project uses Ruff for linting and formatting:
```bash
poetry run ruff check .
poetry run ruff format .
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See the LICENSE file for details.

## Troubleshooting

### Desk Not Found
- Ensure your desk is powered on and Bluetooth is enabled
- Check that your Bluetooth adapter is working
- Try increasing the scan timeout by running discovery multiple times

### Permission Errors (Linux)
On Linux, you may need to grant permissions for BLE access:
```bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python)
```

Or run the application as root (not recommended for regular use).

## Acknowledgments

Built with:
- [Bleak](https://github.com/hbldh/bleak) - Cross-platform BLE library
- [Click](https://click.palletsprojects.com/) - Command-line interface framework
- [Poetry](https://python-poetry.org/) - Dependency management
