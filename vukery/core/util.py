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
