# HA-thermostat-finer-switching-temperature-differential

Finer switching temperature differential for Home Assistant thermostat.

## Problem

Many thermostats have a built-in hysteresis (switching differential) of 1°C or more. This means:
- The thermostat won't start heating until the temperature drops 0.5-1°C below the target
- The thermostat won't stop heating until the temperature rises 0.5-1°C above the target

This results in temperature swings that are larger than desired.

## Solution

This blueprint provides finer temperature control by:
1. **Starting heating earlier**: When the current temperature drops below your target and the thermostat is idle, it temporarily raises the target by 0.5°C to trigger heating sooner.
2. **Stopping heating earlier**: When the current temperature exceeds your target and the thermostat is still heating, it temporarily lowers the target by 0.5°C to stop heating sooner.

After the hvac action changes (or after a 2-minute timeout), the target temperature is restored from a scene snapshot.

## Installation

1. [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FFabianGabor%2FHA-thermostat-finer-switching-temperature-differential%2Fblob%2Fmain%2Fthermostat-finer-switching-temp-diff.yaml)

2. Or manually: Copy `thermostat-finer-switching-temp-diff.yaml` to your `config/blueprints/automation/` directory.

## Configuration

When creating an automation from this blueprint, you'll need to provide:

| Input | Required | Description |
|-------|----------|-------------|
| Thermostat | Yes | The climate entity to control |
| Window Sensor | No | A binary sensor that pauses adjustments when on (window open) |

## How It Works

```
Current Temp > Target AND Heating → Snapshot → Lower target by 0.5°C → Wait for idle → Restore snapshot
Current Temp < Target AND Idle → Snapshot → Raise target by 0.5°C → Wait for heating → Restore snapshot
```

Key design decisions to prevent issues:
- **Triggers on both current_temperature and target temperature changes** - responds to manual target changes within deadzone
- **hvac_action conditions prevent re-triggering** - after adjusting, the hvac state changes (idle↔heating), so the conditions no longer match
- **Scene snapshot created inside each branch** - ensures we capture the state BEFORE any modification
- **mode: single** - prevents concurrent runs while automation is in progress

## Development

### Running Tests

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v
```

### Using the Dev Container

1. Open this repository in VS Code
2. When prompted, click "Reopen in Container"
3. Tests can be run from the integrated terminal

## Changelog

### v2.0.0
- **Fixed**: Temperature drift bug where target kept incrementing
- **Fixed**: Scene snapshot now created inside each choose branch (not at top of action)
- **Removed**: Trigger on target temperature changes (was causing self-triggering loops)
- **Improved**: Increased timeout from 1 minute to 2 minutes
- **Added**: Unavailability check for thermostat
- **Added**: Dynamic scene naming to support multiple thermostats

### v1.0.0
- Initial release
