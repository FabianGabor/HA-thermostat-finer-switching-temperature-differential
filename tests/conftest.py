"""Pytest configuration for Home Assistant blueprint testing."""
import pytest


@pytest.fixture
def blueprint_yaml():
    """Load the blueprint YAML file."""
    import yaml
    from pathlib import Path
    
    blueprint_path = Path(__file__).parent.parent / "thermostat-finer-switching-temp-diff.yaml"
    with open(blueprint_path) as f:
        return yaml.safe_load(f)
