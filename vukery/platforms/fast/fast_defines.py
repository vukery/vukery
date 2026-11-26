# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/platforms/fast/fast_defines.py
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
"""Defines for FAST Pinball hardware."""

HARDWARE_KEY = {
    "neuron":  '2000',
    "sys11":   '1100',
    "wpc89":   '8900',
    "wpc95":   '9500'
}

USB_IDS = {  # (VID, PID)
    (11914, 4155): ('net', 'FAST Neuron Controller'),
    (11914, 4156): ('aud', 'FAST Audio Interface'),
    (11914, 4157): ('exp', 'FAST Expansion Board'),
    (11914, 4158): ('dsp', 'FAST Display Controller'),
    (5824, 1163):  ('net', 'FAST Retro Controller'),  # Teensyduino
    (1027, 24593): ('net', 'FAST Nano Controller'),  # FTDI Quad RS232-HS
}

VALID_IO_BOARDS = (
    'FP-I/O-3208',
    'FP-I/O-1616',
    'FP-I/O-1604',
    'FP-I/O-0804',
    'FP-I/O-0024',
    'FP-CAB-0001',   # Internally the same as FP-I/O-0024
    'FP-RETRO-I/O',  # Fake I/O board for Retro Controllers
)

EXPANSION_BOARD_FEATURES = {
    'FP-EXP-1313': {
        'min_fw': '0.28',
        'local_breakouts': ['FP-EXP-1313'],
        'breakout_ports': 0,
        'default_address': '30'
    },
    'FP-EXP-0051': {
        'min_fw': '0.31',
        'local_breakouts': ['FP-EXP-0051'],
        'breakout_ports': 0,
        'default_address': 'D0'
    },
    'FP-EXP-0061': {
        'min_fw': '0.31',
        'local_breakouts': ['FP-EXP-0061'],
        'breakout_ports': 0,
        'default_address': '90'
    },
    'FP-EXP-0071': {
        'min_fw': '0.11',
        'local_breakouts': ['FP-EXP-0071'],
        'breakout_ports': 0,
        'default_address': 'B4'
    },
    'FP-EXP-0081': {
        'min_fw': '0.12',
        'local_breakouts': ['FP-EXP-0081', 'FP-EXP-0081'],
        'breakout_ports': 0,
        'default_address': '84'
    },
    'FP-EXP-0091': {
        'min_fw': '0.11',
        'local_breakouts': ['FP-EXP-0091'],
        'breakout_ports': 2,
        'default_address': '88'
    },
    'FP-EXP-2000': {
        'min_fw': '0.11',
        'local_breakouts': ['FP-BRK-0001'],
        'breakout_ports': 3,
        'default_address': '48'
    },
}

BREAKOUT_FEATURES = {
    'FP-EXP-1313': {
        'min_fw': '0.44',
        'shaker_ports': 1
    },
    'FP-EXP-0061': {
        'min_fw': '0.33',
        'led_ports': 4,
        'stepper_ports': 2
    },
    'FP-EXP-0071': {
        'min_fw': '0.11',
        'led_ports': 4,
        'servo_ports': 4,
    },
    'FP-EXP-0081': {
        'min_fw': '0.11',
        'led_ports': 4,
    },
    'FP-EXP-0091': {
        'min_fw': '0.11',
        'led_ports': 4,
    },
    'FP-BRK-0001': {  # Neuron
        'min_fw': '0.8',
        'led_ports': 4,
    },
    'FP-DRV-0800': {
        'min_fw': '0.0',
        'servo_ports': 8,
    },
    'FP-BRK-0116': {
        'min_fw': '0.0',
        'flasher_ports': 16,
    },
    # TODO temp module until this code is written
    'FP-PWR-0007': {
        'min_fw': '0.0',
        'device_class': 'mpf.platforms.fast.fast_exp_board',
    },
}

# vukery: the RETRO_* maps were removed (FAST Retro controllers aren't supported).
