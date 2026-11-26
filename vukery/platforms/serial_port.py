"""Real serial ports, for real hardware. Coming with `vuk hardware` (pyserial)."""

from vukery.core.errors import HardwareError
from vukery.platforms.interfaces import SerialPortInfo


async def open_serial(port: str, baud: int):
    raise HardwareError("Real serial ports aren't supported yet. Use the development or test platform.")


def list_serial_ports() -> list[SerialPortInfo]:
    return []
