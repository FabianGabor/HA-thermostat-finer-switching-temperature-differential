"""
Unit tests for the thermostat finer switching temperature differential automation.

These tests simulate the automation logic to verify correct behavior without
requiring a full Home Assistant instance.
"""
import pytest
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class HvacAction(Enum):
    HEATING = "heating"
    IDLE = "idle"


@dataclass
class ThermostatState:
    """Simulates a thermostat entity state."""
    current_temperature: float
    target_temperature: float
    hvac_action: HvacAction
    state: str = "heat"


@dataclass 
class SceneSnapshot:
    """Simulates a scene snapshot."""
    target_temperature: float


@dataclass
class AutomationContext:
    """Context for automation execution."""
    thermostat: ThermostatState
    window_open: bool = False
    temperature_changes: List[float] = field(default_factory=list)
    scene_snapshot: Optional[SceneSnapshot] = None
    is_running: bool = False  # Simulates mode: single
    
    def create_scene_snapshot(self):
        """Simulate scene.create - capture current state."""
        self.scene_snapshot = SceneSnapshot(
            target_temperature=self.thermostat.target_temperature
        )
    
    def restore_scene_snapshot(self):
        """Simulate scene.turn_on - restore captured state."""
        if self.scene_snapshot:
            self.thermostat.target_temperature = self.scene_snapshot.target_temperature
            self.temperature_changes.append(self.scene_snapshot.target_temperature)
    
    def set_temperature(self, temp: float):
        """Simulate climate.set_temperature action."""
        self.temperature_changes.append(temp)
        self.thermostat.target_temperature = temp
        
        # Simulate hvac_action change based on temperature differential
        if temp > self.thermostat.current_temperature:
            self.thermostat.hvac_action = HvacAction.HEATING
        else:
            self.thermostat.hvac_action = HvacAction.IDLE


def simulate_automation(ctx: AutomationContext) -> Optional[str]:
    """
    Simulate the automation logic.
    
    Returns the action taken or None if conditions weren't met.
    """
    # Simulate mode: single - don't run if already running
    if ctx.is_running:
        return None
    
    # Check window condition
    if ctx.window_open:
        return None
    
    # Check thermostat availability
    if ctx.thermostat.state in ['unavailable', 'unknown']:
        return None
    
    current_temp = ctx.thermostat.current_temperature
    target_temp = ctx.thermostat.target_temperature
    hvac_action = ctx.thermostat.hvac_action
    
    # Case 1: Current > target AND heating -> stop heating earlier
    if current_temp > target_temp and hvac_action == HvacAction.HEATING:
        ctx.is_running = True
        # Create snapshot BEFORE changing temperature
        ctx.create_scene_snapshot()
        ctx.set_temperature(target_temp - 0.5)
        # Simulate wait_for_trigger completing (hvac goes to idle)
        ctx.thermostat.hvac_action = HvacAction.IDLE
        # Restore from snapshot
        ctx.restore_scene_snapshot()
        ctx.is_running = False
        return "stop_heating"
    
    # Case 2: Current < target AND idle -> start heating earlier
    if current_temp < target_temp and hvac_action == HvacAction.IDLE:
        ctx.is_running = True
        # Create snapshot BEFORE changing temperature
        ctx.create_scene_snapshot()
        ctx.set_temperature(target_temp + 0.5)
        # Simulate wait_for_trigger completing (hvac goes to heating)
        ctx.thermostat.hvac_action = HvacAction.HEATING
        # Restore from snapshot
        ctx.restore_scene_snapshot()
        ctx.is_running = False
        return "start_heating"
    
    return None


class TestAutomationConditions:
    """Tests for automation trigger conditions."""
    
    def test_window_open_blocks_automation(self):
        """Automation should not run when window is open."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.0,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            ),
            window_open=True
        )
        
        result = simulate_automation(ctx)
        assert result is None
        assert len(ctx.temperature_changes) == 0
    
    def test_unavailable_thermostat_blocks_automation(self):
        """Automation should not run when thermostat is unavailable."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.0,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE,
                state='unavailable'
            )
        )
        
        result = simulate_automation(ctx)
        assert result is None
    
    def test_mode_single_blocks_concurrent_runs(self):
        """Automation should not run if already running (mode: single)."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.0,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            ),
            is_running=True
        )
        
        result = simulate_automation(ctx)
        assert result is None


class TestHeatingStopLogic:
    """Tests for stopping heating when temperature exceeds target."""
    
    def test_stops_heating_when_over_target(self):
        """Should lower target temp when current > target and heating."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.6,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        
        result = simulate_automation(ctx)
        
        assert result == "stop_heating"
        # Should have lowered temp, then restored from snapshot
        assert ctx.temperature_changes == [23.0, 23.5]
        # Final temp should be original target (from snapshot)
        assert ctx.thermostat.target_temperature == 23.5
    
    def test_no_action_when_idle_and_over_target(self):
        """Should not act if already idle when over target."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.6,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        assert result is None


class TestHeatingStartLogic:
    """Tests for starting heating when temperature is below target."""
    
    def test_starts_heating_when_under_target(self):
        """Should raise target temp when current < target and idle."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        
        assert result == "start_heating"
        # Should have raised temp, then restored from snapshot
        assert ctx.temperature_changes == [24.0, 23.5]
        # Final temp should be original target (from snapshot)
        assert ctx.thermostat.target_temperature == 23.5
    
    def test_no_action_when_heating_and_under_target(self):
        """Should not act if already heating when under target."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        
        result = simulate_automation(ctx)
        assert result is None


class TestNoInfiniteLoop:
    """Tests to ensure no infinite adjustment loops."""
    
    def test_target_returns_to_original_value(self):
        """After automation runs, target should be back to original value."""
        original_target = 23.5
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        # Final target should match original
        assert ctx.thermostat.target_temperature == original_target
    
    def test_snapshot_captures_before_modification(self):
        """
        Scene snapshot must be created BEFORE modifying temperature.
        This was the original bug - snapshot was created at start of action,
        capturing already-modified values on subsequent runs.
        """
        original_target = 23.5
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        # Verify snapshot captured the original value
        assert ctx.scene_snapshot.target_temperature == original_target


class TestTriggerBehavior:
    """Tests related to trigger behavior."""
    
    def test_has_both_triggers(self, blueprint_yaml):
        """
        Blueprint should trigger on both current_temperature and target temperature changes.
        """
        triggers = blueprint_yaml['trigger']
        
        # Should have two triggers
        assert len(triggers) == 2
        
        # Find triggers by attribute
        attrs = [t.get('attribute') for t in triggers]
        assert 'current_temperature' in attrs
        assert 'temperature' in attrs
    
    def test_hvac_action_prevents_retriggering(self):
        """
        After automation completes, hvac_action state change prevents re-triggering.
        
        - If we stopped heating (lowered target) → hvac is now 'idle' → won't match 'heating' condition
        - If we started heating (raised target) → hvac is now 'heating' → won't match 'idle' condition
        """
        # Scenario: temp below target, idle → we raise target to start heating
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "start_heating"
        
        # After automation completes, hvac_action is HEATING
        # If triggered again with same conditions...
        assert ctx.thermostat.hvac_action == HvacAction.HEATING
        
        # ...it won't match the "idle" condition, so no action
        result2 = simulate_automation(ctx)
        assert result2 is None


class TestBlueprintStructure:
    """Tests for blueprint YAML structure validity."""
    
    def test_blueprint_has_required_fields(self, blueprint_yaml):
        """Blueprint should have all required fields."""
        assert 'blueprint' in blueprint_yaml
        assert 'name' in blueprint_yaml['blueprint']
        assert 'domain' in blueprint_yaml['blueprint']
        assert blueprint_yaml['blueprint']['domain'] == 'automation'
        assert 'input' in blueprint_yaml['blueprint']
    
    def test_blueprint_uses_scene_not_helper(self, blueprint_yaml):
        """Blueprint should use scene snapshots, not require a helper."""
        inputs = blueprint_yaml['blueprint']['input']
        
        # Should NOT require a target_temp_helper
        assert 'target_temp_helper' not in inputs
        
        # Should have thermostat and optional window_sensor
        assert 'thermostat' in inputs
        assert 'window_sensor' in inputs
    
    def test_scene_created_inside_choose_branches(self, blueprint_yaml):
        """
        Scene should be created inside each choose branch, not at the top.
        This ensures we capture the state BEFORE any modification.
        """
        import yaml
        yaml_str = yaml.dump(blueprint_yaml)
        
        # The action section should have scene.create inside the choose sequences
        # Count occurrences - should be 2 (one in each branch)
        assert yaml_str.count('scene.create') == 2
