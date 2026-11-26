"""FAST Nano, NET port: MPF's ``test_Fast_Nano.py`` scenarios, at the platform level.

Each ``it_`` names the MPF test it comes from. Differences from MPF:
- MPF's config also has a digital output and a motor on driver 0x01. vukery has
  neither device yet, so their two driver commands are left out.
- Flipper and RGB LED scenarios come later (flippers need the device layer,
  LEDs are the next stage).
"""

import pytest

from tests.mpf_ported.fast.mock_fast import MockFastNetNano
from tests.platforms.fast.rig import FastRig, mpf_expected_commands
from vukery.core.errors import CoilLimitError, ConfigError, HardwareError

# MPF's own expected startup traffic for this config, minus the digital output on driver 0x01
STARTUP = {
    command: response
    for command, response in mpf_expected_commands("test_Fast_Nano.py").items()
    if not command.startswith("DN:01,")
}


def make_rig(id_response: str | None = None) -> FastRig:
    net = MockFastNetNano(None)
    if id_response:
        net.autorespond_commands["ID:"] = id_response
    return FastRig("nano.yaml", boards={"com6": net}, expected={"com6": STARTUP})


@pytest.fixture
def rig():
    rig = make_rig()
    rig.start()
    yield rig
    rig.stop()


def describe_fast_nano():
    def describe_startup():
        def it_sends_exactly_the_startup_commands_mpf_expects(rig):  # MPF: setUp
            assert rig.unsent("com6") == {}

        def it_finds_the_io_boards(rig):  # MPF: setUp
            boards = rig.platform.io_boards
            assert [(b.switch_count, b.driver_count) for b in boards.values()] == [
                (32, 8), (8, 4), (16, 16), (16, 16)]

        def it_reports_boards_and_firmware(rig):  # MPF: test_coils (hardware scan)
            assert rig.platform.get_info_string() == (
                'NET: FP-CPU-002-2 v01.05\n'
                '\n'
                'I/O Boards:\n'
                'Board 0 - Model: FP-I/O-3208, Firmware: 01.05, Switches: 32, Drivers: 8\n'
                'Board 1 - Model: FP-I/O-0804, Firmware: 01.05, Switches: 8, Drivers: 4\n'
                'Board 2 - Model: FP-I/O-1616, Firmware: 01.05, Switches: 16, Drivers: 16\n'
                'Board 3 - Model: FP-I/O-1616, Firmware: 01.05, Switches: 16, Drivers: 16\n')

        def it_reads_switch_states_from_the_switch_dump(rig):
            # The SA: dump has switch 0x1A active. s_test_nc is NC, so it reads as inactive.
            assert rig.host.switch_states["s_test_nc"] == 0

        def it_refuses_firmware_older_than_the_nano_minimum():  # a vukery spec
            rig = make_rig(id_response="ID:NET FP-CPU-002-2  01.04")
            with pytest.raises(HardwareError, match="01.05 or newer, but yours is 01.04"):
                rig.start()

    def describe_coils():
        def it_pulses(rig):  # MPF: _test_pulse
            rig.boards["com6"].expected_commands = {"TN:04,01": "TN:P"}
            rig.coils["c_test"].pulse()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_pulses_a_long_pulse_coil_with_a_trigger(rig):  # MPF: _test_long_pulse
            rig.boards["com6"].expected_commands = {"TN:12,01": "TN:P"}
            rig.coils["c_long_pulse"].pulse()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_timed_enables(rig):  # MPF: _test_timed_enable
            rig.boards["com6"].expected_commands = {"DN:16,89,00,10,14,FF,C8,88,00": "DN:P"}
            rig.coils["c_timed_enable"].timed_enable()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_pulses_with_timed_enable_when_configured(rig):  # MPF: _test_default_timed_enable
            rig.boards["com6"].expected_commands = {"DN:17,89,00,10,14,FF,C8,88,00": "DN:P"}
            rig.coils["c_default_timed_enable"].pulse()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_refuses_to_enable_a_coil_without_hold_power(rig):  # MPF: _test_enable_exception
            with pytest.raises(CoilLimitError):
                rig.coils["c_test"].enable()

        def it_enables_a_coil_with_allow_enable(rig):  # MPF: _test_allow_enable
            rig.boards["com6"].expected_commands = {"DN:06,C1,00,18,17,FF,FF,00,00": "DN:P"}
            rig.coils["c_test_allow_enable"].enable()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_enables_with_its_hold_power(rig):  # MPF: _test_pwm_ssm
            rig.boards["com6"].expected_commands = {"DN:13,C1,00,18,0A,FF,88,00,00": "DN:P"}
            rig.coils["c_hold_ssm"].enable()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_refuses_pulse_power_above_one(rig):  # a vukery spec: coil limits
            with pytest.raises(CoilLimitError):
                rig.coils["c_test"].pulse(pulse_power=1.5)

    def describe_hardware_rules():
        def it_sets_two_rules_on_one_switch(rig):  # MPF: _test_two_rules_one_switch
            rig.boards["com6"].expected_commands = {"TN:04,00,03": "TN:P", "TN:06,00,03": "TN:P"}
            rig.enable_autofire("ac_same_switch1")
            rig.enable_autofire("ac_same_switch2")
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_sets_and_clears_a_pulse_rule(rig):  # MPF: _test_hw_rule_pulse
            rig.boards["com6"].expected_commands = {"TN:07,00,16": "TN:P"}
            rig.enable_autofire("ac_slingshot_test")
            rig.settle()
            assert rig.unsent("com6") == {}

            rig.boards["com6"].expected_commands = {"TN:07,02": "TN:P"}
            rig.disable_autofire("ac_slingshot_test")
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_pulses_then_enables_with_pwm(rig):  # MPF: _test_hw_rule_pulse_pwm
            rig.boards["com6"].expected_commands = {"TN:11,01": "TN:P"}
            rig.coils["c_pulse_pwm_mask"].pulse()
            rig.settle()
            assert rig.unsent("com6") == {}

            rig.boards["com6"].expected_commands = {"DN:11,C1,00,18,0A,AA,92,00,00": "DN:P"}
            rig.coils["c_pulse_pwm_mask"].enable()
            rig.settle()
            assert rig.unsent("com6") == {}

        def it_sets_a_rule_on_an_inverted_switch(rig):  # MPF: _test_hw_rule_pulse_inverted_switch
            rig.boards["com6"].expected_commands = {"DN:07,11,1A,10,0A,FF,00,00,00": "DN:P"}
            rig.enable_autofire("ac_inverted_switch")
            rig.settle()
            assert rig.unsent("com6") == {}

        def describe_switches_and_coils_on_different_boards():  # MPF: _test_hw_rule_same_board
            def it_allows_the_first_eight_switches_with_any_board(rig):
                rig.boards["com6"].expected_commands = {"TN:21,00,07": "DN:P"}
                rig.enable_autofire("ac_different_boards")
                rig.settle()
                assert rig.unsent("com6") == {}

            def it_allows_a_switch_and_coil_on_the_same_board(rig):
                rig.boards["com6"].expected_commands = {"TN:21,00,39": "DN:P"}
                rig.enable_autofire("ac_board_3")
                rig.settle()
                assert rig.unsent("com6") == {}

            def it_refuses_other_combinations(rig):
                with pytest.raises(ConfigError, match="different boards"):
                    rig.enable_autofire("ac_broken_combination")

    def describe_switches():
        def it_reports_a_switch_closing_and_opening(rig):  # MPF: _test_switch_changes
            net = rig.platform.serial_connections["net"]
            net.parse_incoming_raw_bytes(b"-N:07\r")
            assert rig.host.switch_states["s_test"] == 1
            net.parse_incoming_raw_bytes(b"/N:07\r")
            assert rig.host.switch_states["s_test"] == 0
            assert rig.host.switch_events == [("s_test", 1), ("s_test", 0)]

        def it_reports_nc_switches_as_logical_states(rig):  # MPF: _test_switch_changes_nc
            net = rig.platform.serial_connections["net"]
            net.parse_incoming_raw_bytes(b"-N:1A\r")
            assert rig.host.switch_states["s_test_nc"] == 1
            net.parse_incoming_raw_bytes(b"/N:1A\r")
            assert rig.host.switch_states["s_test_nc"] == 0

    def describe_reboot():
        def it_stops_the_machine_when_the_nano_reboots(rig):  # MPF: test_nano_reboot
            rig.boards["com6"].queue.append("!B:00")
            rig.settle()
            assert rig.host.stopped == "FAST NET Nano rebooted"
