"""Pytest configuration for Home Assistant blueprint testing."""
import pytest
import yaml
from pathlib import Path


class HomeAssistantLoader(yaml.SafeLoader):
    """Custom YAML loader that handles Home Assistant custom tags."""
    pass


def input_constructor(loader, node):
    """Handle !input tags by returning a placeholder dict."""
    return {"__input__": loader.construct_scalar(node)}


# Register the !input constructor
HomeAssistantLoader.add_constructor("!input", input_constructor)


@pytest.fixture
def blueprint_yaml():
    """Load the blueprint YAML file."""
    blueprint_path = Path(__file__).parent.parent / "thermostat-finer-switching-temp-diff.yaml"
    with open(blueprint_path) as f:
        return yaml.load(f, Loader=HomeAssistantLoader)
