"""
Unit tests for the thermostat finer switching temperature differential automation.

These tests simulate the automation logic to verify correct behavior without
requiring a full Home Assistant instance.
"""
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


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_exact_temperature_match_no_action(self):
        """When current temp equals target, no action should be taken."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.5,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        
        result = simulate_automation(ctx)
        assert result is None
        assert len(ctx.temperature_changes) == 0
    
    def test_very_small_temperature_difference_over(self):
        """Should trigger even with very small temperature overshoot."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.51,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "stop_heating"
    
    def test_very_small_temperature_difference_under(self):
        """Should trigger even with very small temperature undershoot."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.49,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "start_heating"
    
    def test_unknown_thermostat_state_blocks_automation(self):
        """Automation should not run when thermostat state is unknown."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.0,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE,
                state='unknown'
            )
        )
        
        result = simulate_automation(ctx)
        assert result is None
    
    def test_negative_temperatures(self):
        """Should handle negative temperatures correctly."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=-5.0,
                target_temperature=-4.0,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "start_heating"
        # Should have raised temp to -3.5, then restored to -4.0
        assert ctx.temperature_changes == [-3.5, -4.0]
    
    def test_high_temperatures(self):
        """Should handle high temperatures correctly."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=35.1,
                target_temperature=35.0,
                hvac_action=HvacAction.HEATING
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "stop_heating"
        # Should have lowered temp to 34.5, then restored to 35.0
        assert ctx.temperature_changes == [34.5, 35.0]
    
    def test_zero_target_temperature(self):
        """Should handle target temperature of zero correctly."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=-0.5,
                target_temperature=0.0,
                hvac_action=HvacAction.IDLE
            )
        )
        
        result = simulate_automation(ctx)
        assert result == "start_heating"
        # Should have raised temp to 0.5, then restored to 0.0
        assert ctx.temperature_changes == [0.5, 0.0]


class TestTemperatureAdjustmentValues:
    """Tests to verify the temperature adjustment delta is correct."""
    
    def test_stop_heating_lowers_by_half_degree(self):
        """When stopping heating, target should be lowered by 0.5°."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=22.1,
                target_temperature=22.0,
                hvac_action=HvacAction.HEATING
            )
        )
        
        simulate_automation(ctx)
        
        # First change should be target - 0.5
        assert ctx.temperature_changes[0] == 21.5
    
    def test_start_heating_raises_by_half_degree(self):
        """When starting heating, target should be raised by 0.5°."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=21.9,
                target_temperature=22.0,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        # First change should be target + 0.5
        assert ctx.temperature_changes[0] == 22.5


class TestSceneSnapshotBehavior:
    """Tests for scene snapshot functionality."""
    
    def test_scene_snapshot_created_on_stop_heating(self):
        """Scene snapshot should be created when stopping heating."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.6,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        
        simulate_automation(ctx)
        
        assert ctx.scene_snapshot is not None
        assert ctx.scene_snapshot.target_temperature == 23.5
    
    def test_scene_snapshot_created_on_start_heating(self):
        """Scene snapshot should be created when starting heating."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        assert ctx.scene_snapshot is not None
        assert ctx.scene_snapshot.target_temperature == 23.5
    
    def test_scene_not_created_when_no_action(self):
        """Scene snapshot should not be created when no action is taken."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.5,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        assert ctx.scene_snapshot is None


class TestMultipleRuns:
    """Tests for behavior across multiple automation runs."""
    
    def test_consecutive_runs_maintain_original_target(self):
        """Multiple runs should always restore to original target."""
        original_target = 22.0
        
        # First run - start heating
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=21.5,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        assert ctx.thermostat.target_temperature == original_target
        
        # Simulate temperature drop again, hvac went idle again
        ctx.thermostat.current_temperature = 21.8
        ctx.thermostat.hvac_action = HvacAction.IDLE
        ctx.temperature_changes.clear()
        
        simulate_automation(ctx)
        assert ctx.thermostat.target_temperature == original_target
    
    def test_alternating_heating_states(self):
        """Test alternating between start and stop heating scenarios."""
        target = 22.0
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=21.5,
                target_temperature=target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        # Run 1: Start heating (current < target, idle)
        result1 = simulate_automation(ctx)
        assert result1 == "start_heating"
        assert ctx.thermostat.target_temperature == target
        
        # Simulate overshoot
        ctx.thermostat.current_temperature = 22.5
        ctx.thermostat.hvac_action = HvacAction.HEATING
        ctx.temperature_changes.clear()
        
        # Run 2: Stop heating (current > target, heating)
        result2 = simulate_automation(ctx)
        assert result2 == "stop_heating"
        assert ctx.thermostat.target_temperature == target


class TestBlueprintConfiguration:
    """Tests for blueprint configuration details."""
    
    def test_blueprint_mode_is_single(self, blueprint_yaml):
        """Blueprint should use mode: single to prevent concurrent runs."""
        assert blueprint_yaml.get('mode') == 'single'
    
    def test_triggers_have_delay(self, blueprint_yaml):
        """Triggers should have a delay to prevent rapid firing."""
        triggers = blueprint_yaml['trigger']
        
        for trigger in triggers:
            assert 'for' in trigger
            # Total delay should be 15 seconds
            delay = trigger['for']
            total_seconds = (
                delay.get('hours', 0) * 3600 +
                delay.get('minutes', 0) * 60 +
                delay.get('seconds', 0)
            )
            assert total_seconds == 15
    
    def test_wait_for_trigger_has_timeout(self, blueprint_yaml):
        """wait_for_trigger should have a timeout to prevent hanging."""
        import yaml
        yaml_str = yaml.dump(blueprint_yaml)
        
        # Should have timeout configuration
        assert 'timeout' in yaml_str
        assert 'continue_on_timeout' in yaml_str
    
    def test_window_sensor_is_optional(self, blueprint_yaml):
        """Window sensor input should have a default value (optional)."""
        inputs = blueprint_yaml['blueprint']['input']
        window_input = inputs.get('window_sensor', {})
        
        # Should have default: null to make it optional
        assert 'default' in window_input
    
    def test_thermostat_selector_is_climate_domain(self, blueprint_yaml):
        """Thermostat input should use climate domain selector."""
        inputs = blueprint_yaml['blueprint']['input']
        thermostat_input = inputs.get('thermostat', {})
        
        assert 'selector' in thermostat_input
        assert 'entity' in thermostat_input['selector']
        assert thermostat_input['selector']['entity']['domain'] == 'climate'
    
    def test_window_sensor_selector_is_binary_sensor(self, blueprint_yaml):
        """Window sensor input should use binary_sensor domain selector."""
        inputs = blueprint_yaml['blueprint']['input']
        window_input = inputs.get('window_sensor', {})
        
        assert 'selector' in window_input
        assert 'entity' in window_input['selector']
        assert window_input['selector']['entity']['domain'] == 'binary_sensor'
    
    def test_blueprint_has_source_url(self, blueprint_yaml):
        """Blueprint should have a source_url for attribution."""
        assert 'source_url' in blueprint_yaml['blueprint']
        assert 'github.com' in blueprint_yaml['blueprint']['source_url']
    
    def test_blueprint_has_description(self, blueprint_yaml):
        """Blueprint should have a meaningful description."""
        assert 'description' in blueprint_yaml['blueprint']
        description = blueprint_yaml['blueprint']['description']
        assert len(description) > 50  # Should be meaningful, not just a few words
    
    def test_blueprint_has_cooldown_condition(self, blueprint_yaml):
        """
        Blueprint should have a cooldown condition to prevent self-triggering loops.
        
        This prevents the runaway effect where the automation keeps re-triggering
        on its own restore action after a timeout.
        """
        import yaml
        yaml_str = yaml.dump(blueprint_yaml)
        
        # Should have last_triggered check for cooldown
        assert 'last_triggered' in yaml_str
        # Should reference 'this.attributes' for self-reference
        assert 'this' in yaml_str


class TestHvacActionStates:
    """Tests for different HVAC action states."""
    
    def test_only_heating_and_idle_trigger_actions(self):
        """Only heating and idle hvac_action states should trigger actions."""
        # Test with heating state - should trigger if over target
        ctx_heating = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.6,
                target_temperature=23.5,
                hvac_action=HvacAction.HEATING
            )
        )
        assert simulate_automation(ctx_heating) == "stop_heating"
        
        # Test with idle state - should trigger if under target
        ctx_idle = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        assert simulate_automation(ctx_idle) == "start_heating"


class TestIsRunningFlag:
    """Tests for the is_running flag (mode: single simulation)."""
    
    def test_is_running_false_after_automation_completes(self):
        """is_running flag should be False after automation completes."""
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            )
        )
        
        simulate_automation(ctx)
        
        assert ctx.is_running is False
    
    def test_is_running_set_during_execution(self):
        """is_running should be True during execution (checked indirectly)."""
        # We can't directly observe this mid-execution in our simple simulation,
        # but we verify that starting with is_running=True blocks execution
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=23.5,
                hvac_action=HvacAction.IDLE
            ),
            is_running=True
        )
        
        result = simulate_automation(ctx)
        assert result is None


def simulate_automation_with_timeout(
    ctx: AutomationContext, 
    thermostat_responds: bool = True
) -> Optional[str]:
    """
    Simulate automation with timeout behavior.
    
    When thermostat_responds=False, simulates the wait_for_trigger timing out
    (thermostat never changes hvac_action).
    """
    if ctx.is_running:
        return None
    if ctx.window_open:
        return None
    if ctx.thermostat.state in ['unavailable', 'unknown']:
        return None
    
    current_temp = ctx.thermostat.current_temperature
    target_temp = ctx.thermostat.target_temperature
    hvac_action = ctx.thermostat.hvac_action
    
    if current_temp > target_temp and hvac_action == HvacAction.HEATING:
        ctx.is_running = True
        ctx.create_scene_snapshot()
        ctx.set_temperature(target_temp - 0.5)
        
        if thermostat_responds:
            ctx.thermostat.hvac_action = HvacAction.IDLE
        # If not responding, hvac_action stays as HEATING but temp was lowered
        # After timeout, we still restore
        
        ctx.restore_scene_snapshot()
        ctx.is_running = False
        return "stop_heating"
    
    if current_temp < target_temp and hvac_action == HvacAction.IDLE:
        ctx.is_running = True
        ctx.create_scene_snapshot()
        ctx.set_temperature(target_temp + 0.5)
        
        if thermostat_responds:
            ctx.thermostat.hvac_action = HvacAction.HEATING
        # If not responding, hvac_action stays as IDLE
        # After timeout, we still restore (continue_on_timeout: true)
        
        ctx.restore_scene_snapshot()
        ctx.is_running = False
        return "start_heating"
    
    return None


class TestRunawayPrevention:
    """
    Tests to prevent runaway temperature escalation.
    
    Based on real-world bug from history.csv where target temp escalated from
    23.5 → 24 → 24.5 → 25 → 25.5 → 26 while thermostat stayed idle.
    """
    
    def test_timeout_scenario_no_escalation(self):
        """
        When thermostat doesn't respond (timeout), target should return to original.
        
        Scenario from history.csv at 09:23:38:
        - current_temp=23.4, target=23.5, hvac_action=idle
        - Automation raises target to 24.0
        - Thermostat never starts heating (stays idle)
        - After timeout, target should restore to 23.5, NOT stay at 24.0
        """
        original_target = 23.5
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        # Simulate with timeout (thermostat doesn't respond)
        result = simulate_automation_with_timeout(ctx, thermostat_responds=False)
        
        assert result == "start_heating"
        # After timeout + restore, target should be back to original
        assert ctx.thermostat.target_temperature == original_target
    
    def test_repeated_timeout_no_escalation(self):
        """
        Multiple timeouts should not cause target temperature to escalate.
        
        This tests the exact bug scenario: if automation runs multiple times
        with timeouts, target should always return to original value.
        """
        original_target = 23.5
        
        for run in range(5):  # Simulate 5 consecutive automation runs
            ctx = AutomationContext(
                thermostat=ThermostatState(
                    current_temperature=23.4,  # Always below target
                    target_temperature=original_target,
                    hvac_action=HvacAction.IDLE  # Thermostat never responds
                )
            )
            
            simulate_automation_with_timeout(ctx, thermostat_responds=False)
            
            # After each run, target should still be at original
            assert ctx.thermostat.target_temperature == original_target, \
                f"Run {run + 1}: Expected {original_target}, got {ctx.thermostat.target_temperature}"
    
    def test_history_csv_scenario_simulation(self):
        """
        Simulate the exact sequence from history.csv to ensure no runaway.
        
        At 09:23:38: current=23.4, target=23.5, idle
        At 09:23:54: target changed to 24 (automation raised it)
        At 09:25:09: current=22.9, target=24, idle (still not heating!)
        At 09:25:24: target changed to 24.5 (escalation!)
        
        This should NOT happen - target should stay at 23.5.
        """
        # Initial state from history
        original_target = 23.5
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        # Run 1: Automation tries to start heating
        simulate_automation_with_timeout(ctx, thermostat_responds=False)
        assert ctx.thermostat.target_temperature == original_target
        
        # Temperature drops further, but target should still be original
        ctx.thermostat.current_temperature = 22.9
        ctx.thermostat.hvac_action = HvacAction.IDLE
        
        # Run 2: Should not escalate
        simulate_automation_with_timeout(ctx, thermostat_responds=False)
        assert ctx.thermostat.target_temperature == original_target
        
        # Run 3, 4, 5: Continue checking
        for _ in range(3):
            ctx.thermostat.current_temperature -= 0.1
            simulate_automation_with_timeout(ctx, thermostat_responds=False)
            assert ctx.thermostat.target_temperature == original_target
    
    def test_snapshot_captures_pre_modification_value(self):
        """
        Scene snapshot MUST capture the target temperature BEFORE any modification.
        
        The bug occurred because snapshot was created after the temperature
        was already modified in a previous run.
        """
        original_target = 23.5
        ctx = AutomationContext(
            thermostat=ThermostatState(
                current_temperature=23.4,
                target_temperature=original_target,
                hvac_action=HvacAction.IDLE
            )
        )
        
        # First run
        simulate_automation_with_timeout(ctx, thermostat_responds=False)
        
        # The snapshot should have captured the ORIGINAL target
        assert ctx.scene_snapshot is not None
        assert ctx.scene_snapshot.target_temperature == original_target
        
        # Final target should also be original
        assert ctx.thermostat.target_temperature == original_target
