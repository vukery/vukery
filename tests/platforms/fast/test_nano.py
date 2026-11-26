"""FAST Nano, NET port: MPF's ``test_Fast_Nano.py`` scenarios, at the platform level.

Each ``it_`` names the MPF test it comes from. Differences from MPF:
- MPF's config also has a digital output and a motor on driver 0x01. vukery has
  neither device yet, so their two driver commands are left out.
- Flipper scenarios come later (they need the flipper device).
"""

import pytest

from tests.mpf_ported.fast.mock_fast import MockFastNetNano, MockFastRgb
from tests.platforms.fast.rig import FastRig, SilentBoard, mpf_expected_commands
from vukery.core.errors import CoilLimitError, ConfigError, HardwareError
from vukery.devices.coil import Coil, CoilConfig
from vukery.platforms.interfaces import SerialPortInfo, SwitchConfig
from vukery.testing import expect

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
    return FastRig("nano.yaml", boards={"com6": net, "com5": MockFastRgb(None)}, expected={"com6": STARTUP})


@pytest.fixture
def rig():
    rig = make_rig()
    rig.start()
    yield rig
    rig.stop()


def describe_fast_nano():
    def describe_startup():
        def it_sends_exactly_the_startup_commands_mpf_expects(rig):  # MPF: setUp
            expect(rig.unsent("com6")).to_equal({})

        def it_finds_the_io_boards(rig):  # MPF: setUp
            boards = rig.platform.io_boards
            expect([(b.switch_count, b.driver_count) for b in boards.values()]).to_equal([
                (32, 8), (8, 4), (16, 16), (16, 16)])

        def it_reports_boards_and_firmware(rig):  # MPF: test_coils (hardware scan)
            expect(rig.platform.get_info_string()).to_equal('NET: FP-CPU-002-2 v01.05\n'
                'RGB: FP-CPU-002-2 v01.00\n'
                '\n'
                'I/O Boards:\n'
                'Board 0 - Model: FP-I/O-3208, Firmware: 01.05, Switches: 32, Drivers: 8\n'
                'Board 1 - Model: FP-I/O-0804, Firmware: 01.05, Switches: 8, Drivers: 4\n'
                'Board 2 - Model: FP-I/O-1616, Firmware: 01.05, Switches: 16, Drivers: 16\n'
                'Board 3 - Model: FP-I/O-1616, Firmware: 01.05, Switches: 16, Drivers: 16\n')

        def it_reads_switch_states_from_the_switch_dump(rig):
            # The SA: dump has switch 0x1A active. s_test_nc is NC, so it reads as inactive.
            expect(rig.host.switch_states["s_test_nc"]).to_equal(0)

        def it_refuses_firmware_older_than_the_nano_minimum():  # a vukery spec
            rig = make_rig(id_response="ID:NET FP-CPU-002-2  01.04")
            with pytest.raises(HardwareError, match="01.05 or newer, but yours is 01.04"):
                rig.start()

    def describe_coils():
        def it_pulses(rig):  # MPF: _test_pulse
            rig.boards["com6"].expected_commands = {"TN:04,01": "TN:P"}
            rig.coils["c_test"].pulse()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_pulses_a_long_pulse_coil_with_a_trigger(rig):  # MPF: _test_long_pulse
            rig.boards["com6"].expected_commands = {"TN:12,01": "TN:P"}
            rig.coils["c_long_pulse"].pulse()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_timed_enables(rig):  # MPF: _test_timed_enable
            rig.boards["com6"].expected_commands = {"DN:16,89,00,10,14,FF,C8,88,00": "DN:P"}
            rig.coils["c_timed_enable"].timed_enable()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_pulses_with_timed_enable_when_configured(rig):  # MPF: _test_default_timed_enable
            rig.boards["com6"].expected_commands = {"DN:17,89,00,10,14,FF,C8,88,00": "DN:P"}
            rig.coils["c_default_timed_enable"].pulse()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_refuses_to_enable_a_coil_without_hold_power(rig):  # MPF: _test_enable_exception
            with pytest.raises(CoilLimitError):
                rig.coils["c_test"].enable()

        def it_enables_a_coil_with_allow_enable(rig):  # MPF: _test_allow_enable
            rig.boards["com6"].expected_commands = {"DN:06,C1,00,18,17,FF,FF,00,00": "DN:P"}
            rig.coils["c_test_allow_enable"].enable()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_enables_with_its_hold_power(rig):  # MPF: _test_pwm_ssm
            rig.boards["com6"].expected_commands = {"DN:13,C1,00,18,0A,FF,88,00,00": "DN:P"}
            rig.coils["c_hold_ssm"].enable()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_refuses_pulse_power_above_one(rig):  # a vukery spec: coil limits
            with pytest.raises(CoilLimitError):
                rig.coils["c_test"].pulse(pulse_power=1.5)

    def describe_hardware_rules():
        def it_sets_two_rules_on_one_switch(rig):  # MPF: _test_two_rules_one_switch
            rig.boards["com6"].expected_commands = {"TN:04,00,03": "TN:P", "TN:06,00,03": "TN:P"}
            rig.enable_autofire("ac_same_switch1")
            rig.enable_autofire("ac_same_switch2")
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_sets_and_clears_a_pulse_rule(rig):  # MPF: _test_hw_rule_pulse
            rig.boards["com6"].expected_commands = {"TN:07,00,16": "TN:P"}
            rig.enable_autofire("ac_slingshot_test")
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

            rig.boards["com6"].expected_commands = {"TN:07,02": "TN:P"}
            rig.disable_autofire("ac_slingshot_test")
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_pulses_then_enables_with_pwm(rig):  # MPF: _test_hw_rule_pulse_pwm
            rig.boards["com6"].expected_commands = {"TN:11,01": "TN:P"}
            rig.coils["c_pulse_pwm_mask"].pulse()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

            rig.boards["com6"].expected_commands = {"DN:11,C1,00,18,0A,AA,92,00,00": "DN:P"}
            rig.coils["c_pulse_pwm_mask"].enable()
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def it_sets_a_rule_on_an_inverted_switch(rig):  # MPF: _test_hw_rule_pulse_inverted_switch
            rig.boards["com6"].expected_commands = {"DN:07,11,1A,10,0A,FF,00,00,00": "DN:P"}
            rig.enable_autofire("ac_inverted_switch")
            rig.settle()
            expect(rig.unsent("com6")).to_equal({})

        def describe_switches_and_coils_on_different_boards():  # MPF: _test_hw_rule_same_board
            def it_allows_the_first_eight_switches_with_any_board(rig):
                rig.boards["com6"].expected_commands = {"TN:21,00,07": "DN:P"}
                rig.enable_autofire("ac_different_boards")
                rig.settle()
                expect(rig.unsent("com6")).to_equal({})

            def it_allows_a_switch_and_coil_on_the_same_board(rig):
                rig.boards["com6"].expected_commands = {"TN:21,00,39": "DN:P"}
                rig.enable_autofire("ac_board_3")
                rig.settle()
                expect(rig.unsent("com6")).to_equal({})

            def it_refuses_other_combinations(rig):
                with pytest.raises(ConfigError, match="different boards"):
                    rig.enable_autofire("ac_broken_combination")

    def describe_flippers():
        def it_drives_a_single_wound_flipper(rig):  # MPF: test_flipper_single_coil
            main = rig.coils["c_flipper_main"]
            rule = rig.flipper_rule("c_flipper_main", "s_flipper", pulse_ms=11)

            rig.expect("com6", {"TN:20,01": "TN:P"})                        # a manual flip, no rule
            main.pulse()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"DN:20,C1,00,18,0A,FF,01,00,00": "DN:P"})  # manual enable, no rule
            main.enable()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,02": "TN:P"})                        # manual disable
            main.disable()
            expect(rig.sent("com6")).to_be_true()

            rig.expect("com6", {"DN:20,01,01,18,0B,FF,01,00,00": "DN:P"})  # the flipper rule
            rig.platform.set_pulse_on_hit_and_enable_and_release_rule(*rule)
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"DN:20,09,01,18,0A,FF,01,00,00": "DN:P",   # a manual flip under the rule...
                                "DN:20,01,01,18,0B,FF,01,00,00": "DN:P"})  # ...then the rule comes back
            main.pulse()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,01": "TN:P"})                        # the rule's own pulse: no reconfigure
            main.pulse(11)
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,03": "TN:P"})                        # enable with the rule's pulse
            main.enable(pulse_ms=11)
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,02": "TN:P"})
            main.disable()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"DN:20,C1,01,18,0A,FF,01,00,00": "DN:P"})  # enable with a different pulse
            main.enable()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"DN:20,01,01,18,0B,FF,01,00,00": "DN:P"})  # disabling restores the rule
            main.disable()
            expect(rig.sent("com6")).to_be_true()

            rig.expect("com6", {"TN:20,02": "TN:P"})                        # the rule off
            rig.platform.clear_hw_rule(*rule)
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"DN:20,89,01,18,0A,FF,01,00,00": "DN:P"})  # a manual flip, reconfigured
            main.pulse()
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,01": "TN:P"})                        # and again, from the cached config
            main.pulse()
            expect(rig.sent("com6")).to_be_true()

        def it_drives_a_dual_wound_flipper(rig):  # MPF: test_flipper_two_coils
            main = rig.flipper_rule("c_flipper_main", "s_flipper", hold=False)
            hold = rig.flipper_rule("c_flipper_hold", "s_flipper")
            rig.expect("com6", {"DN:20,01,01,18,0A,FF,00,00,00": "DN:P",   # main: pulse, cancel on release
                                "DN:21,01,01,18,0A,FF,01,00,00": "DN:P"})  # hold: pulse, hold, release
            rig.platform.set_pulse_on_hit_and_release_rule(*main)
            rig.platform.set_pulse_on_hit_and_enable_and_release_rule(*hold)
            expect(rig.sent("com6")).to_be_true()
            rig.expect("com6", {"TN:20,02": "TN:P", "TN:21,02": "TN:P"})
            rig.platform.clear_hw_rule(*main)
            rig.platform.clear_hw_rule(*hold)
            expect(rig.sent("com6")).to_be_true()

    def describe_numbers():  # what a typo in a machine's wiring config gets you
        def _switch(rig, number):
            return rig.platform.configure_switch(number, SwitchConfig(name="s_typo", invert=False, debounce="auto"))

        def _coil(rig, number):
            return Coil(CoilConfig.from_yaml("c_typo", {"number": number}), rig.platform,
                        rig.platform.features["max_pulse"])

        def it_numbers_switches_by_board_and_position(rig):
            expect(_switch(rig, "1616_2-3").number).to_equal(_switch(rig, "1616_2-3").number)

        @pytest.mark.parametrize(("number", "message"), [
            ("3208-40", "only has switches 0-31"),
            ("nope-1", "Board nope does not exist"),
            ("7F", "Could not parse switch number s_typo/7F"),
        ])
        def it_explains_a_switch_that_doesnt_exist(rig, number, message):
            with pytest.raises(ConfigError, match=message):
                _switch(rig, number)

        @pytest.mark.parametrize(("number", "message"), [
            ("3208-40", "only has drivers 0-7"),
            ("nope-1", "I/O Board nope does not exist"),
        ])
        def it_explains_a_driver_that_doesnt_exist(rig, number, message):
            with pytest.raises(ConfigError, match=message):
                _coil(rig, number)

        def it_takes_a_plain_hex_driver_number(rig):  # a driver number without a board
            expect(_coil(rig, "05").hw_driver.number).to_equal(5)

    def describe_switches():
        def it_reports_a_switch_closing_and_opening(rig):  # MPF: _test_switch_changes
            net = rig.platform.serial_connections["net"]
            net.parse_incoming_raw_bytes(b"-N:07\r")
            expect(rig.host.switch_states["s_test"]).to_equal(1)
            net.parse_incoming_raw_bytes(b"/N:07\r")
            expect(rig.host.switch_states["s_test"]).to_equal(0)
            expect(rig.host.switch_events).to_equal([("s_test", 1), ("s_test", 0)])

        def it_reports_nc_switches_as_logical_states(rig):  # MPF: _test_switch_changes_nc
            net = rig.platform.serial_connections["net"]
            net.parse_incoming_raw_bytes(b"-N:1A\r")
            expect(rig.host.switch_states["s_test_nc"]).to_equal(1)
            net.parse_incoming_raw_bytes(b"/N:1A\r")
            expect(rig.host.switch_states["s_test_nc"]).to_equal(0)

    def describe_reboot():
        def it_stops_the_machine_when_the_nano_reboots(rig):  # MPF: test_nano_reboot
            rig.boards["com6"].queue.append("!B:00")
            rig.settle()
            expect(rig.host.stopped).to_equal("FAST NET Nano rebooted")

        def it_only_logs_an_rgb_processor_reboot(rig):  # MPF: test_bootloader_crash_ignored
            rig.boards["com5"].queue.append("!B:00")
            rig.settle()
            expect(rig.host.stopped).to_be_none()

    def describe_leds():  # MPF: test_leds
        def _leds(rig):
            return rig.boards["com5"].leds

        def it_maps_old_style_and_one_based_numbers(rig):
            expect(rig.lights["old_style_number"].hw_drivers["red"][0].number).to_equal("00-0")
            expect(rig.lights["test_max_1_based"].hw_drivers["red"][0].number).to_equal("FF-0")

        def it_turns_leds_on_and_off(rig):
            rig.lights["test_led"].on()
            rig.settle(0.1)
            expect(_leds(rig)["97"]).to_equal("FFFFFF")
            expect(_leds(rig)["98"]).to_equal("000000")
            rig.lights["test_led"].off()
            rig.settle(0.1)
            expect(_leds(rig)["97"]).to_equal("000000")

        def it_sets_colors_in_channel_order(rig):
            rig.lights["test_led"].color("112233")
            rig.lights["test_led2"].color("001122")
            rig.lights["test_led2"].color((2, 23, 42))
            rig.settle(0.1)
            expect(_leds(rig)["97"]).to_equal("112233")
            expect(_leds(rig)["98"]).to_equal("17022A")  # GRB, so not 02172A

        def it_fades(rig):
            light = rig.lights["test_led2"]
            light.color((100, 100, 100), fade_ms=100)
            rig.settle(0.03)
            first = int(_leds(rig)["98"][0:2], 16)
            rig.settle(0.03)
            second = int(_leds(rig)["98"][0:2], 16)
            rig.settle(0.2)
            expect(0 < first < second < 100).to_be_true()
            expect(_leds(rig)["98"]).to_equal("646464")

        def describe_rgbw():
            def it_assigns_channels_in_sequence(rig):
                def numbers(name):
                    drivers = rig.lights[name].hw_drivers
                    return [drivers[color][0].number for color in ("red", "green", "blue", "white")]
                expect(numbers("test_rgbw1")).to_equal(["21-0", "21-1", "21-2", "22-0"])
                expect(numbers("test_rgbw2")).to_equal(["22-1", "22-2", "23-0", "23-1"])
                expect(numbers("test_rgbw3")).to_equal(["23-2", "24-0", "24-1", "24-2"])
                expect(numbers("test_rgbw4")).to_equal(["25-0", "25-1", "25-2", "26-0"])
                expect(numbers("test_rgbw5")).to_equal(["28-0", "28-2", "28-1", "29-2"])

            def it_puts_shared_white_on_the_white_channel(rig):
                rig.lights["test_rgbw1"].color("ffffff")
                rig.settle(0.1)
                expect(_leds(rig)["21"]).to_equal("000000")
                expect(_leds(rig)["22"]).to_equal("FF0000")
                rig.lights["test_rgbw2"].color("445566")
                rig.settle(0.1)
                expect(_leds(rig)["22"]).to_equal("FF0011")
                expect(_leds(rig)["23"]).to_equal("224400")

            def it_handles_explicit_channels(rig):
                rig.lights["test_rgbw5"].color("ffffff")
                rig.settle(0.1)
                expect(_leds(rig)["28"]).to_equal("000000")
                expect(_leds(rig)["29"]).to_equal("0000FF")
                rig.lights["test_rgbw5"].color("223344")
                rig.settle(0.1)
                expect(_leds(rig)["28"]).to_equal("002211")
                expect(_leds(rig)["29"]).to_equal("000022")


# A Nano is one FTDI quad serial chip on USB: four ports, of which NET and RGB answer.
NANO_USB = (1027, 24593)
NANO_PORTS = [SerialPortInfo(f"/dev/ttyUSB{i}", *NANO_USB) for i in range(4)]


def describe_port_auto_detection():  # COMBAT's config uses port: auto for net and rgb
    def _rig(serial_ports):
        boards = {"/dev/ttyUSB0": SilentBoard(None), "/dev/ttyUSB1": MockFastNetNano(None),
                  "/dev/ttyUSB2": MockFastRgb(None), "/dev/ttyUSB3": SilentBoard(None)}
        return FastRig("nano.yaml", boards=boards, expected={"/dev/ttyUSB1": STARTUP},
                       serial_ports=serial_ports, auto_ports=True)

    def it_finds_the_net_and_rgb_ports_of_a_nano():
        rig = _rig(NANO_PORTS)
        rig.start()
        try:
            expect(rig.platform.config.net.port).to_equal(["/dev/ttyUSB1"])
            expect(rig.platform.config.rgb.port).to_equal(["/dev/ttyUSB2"])
            expect(rig.unsent("/dev/ttyUSB1")).to_equal({})
        finally:
            rig.stop()

    def it_ignores_serial_devices_that_arent_fast():
        other = SerialPortInfo("/dev/ttyACM9", 0x2341, 0x0043)  # e.g. an Arduino
        rig = _rig([other, *NANO_PORTS])
        rig.start()
        try:
            expect(rig.platform.config.net.port).to_equal(["/dev/ttyUSB1"])
        finally:
            rig.stop()

    def it_explains_when_no_controller_is_attached():
        rig = _rig([])
        with pytest.raises(HardwareError, match="Couldn't find the FAST NET, RGB port"):
            rig.start()
