# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/core/utility_functions.py#L293-L310
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
    @staticmethod
    def hex_string_to_int(inputstring: str, maxvalue: int = 255) -> int:
        """Take a string input of hex numbers and an integer.

        Args:
        ----
            inputstring: A string of incoming hex colors, like ffff00.
            maxvalue: Integer of the max value you'd like to return. Default is
                255. (This is the real value of why this method exists.)

        Returns integer representation of the hex string.
        """
        return_int = int(str(inputstring), 16)

        if return_int > maxvalue:
            return_int = maxvalue

        return return_int

# Copied from the Mission Pinball Framework (MPF) 0.57.6:
# https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/core/utility_functions.py#L336-L351
# Copyright (c) The Mission Pinball Framework team and other contributors.
# MIT License: see vukery/_mpf/NOTICE.
    @staticmethod
    def int_to_hex_string(source_int: int, allow_overflow: bool = False) -> str:
        """Convert an int from 0-255 to a one-byte (2 chars) hex string, with uppercase characters.

        Args:
        ----
            source_int: The integer to convert to a hex string
            allow_overflow: If true, allow an integer of any size to be converted.
                If false (default), only integers 0-255 are allowed.
        """
        source_int = int(source_int)

        if 0 <= source_int <= 255 or allow_overflow:
            return f"{source_int:02X}"

        raise ValueError("invalid source int: %s" % source_int)
