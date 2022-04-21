import spidev

class MAX31855SPIPiHW:

    def __init__(self, bus: int, device: int) -> None:
        self.bus = bus
        self.device = device
        self.spi = spidev.SpiDev()
        # open the spi device
        self.spi.open(self.bus, self.device)
        self.spi.max_speed_hz = 2000000
        self.spi.mode = 0

    def read(self) -> int:
        """
        Read a datagram from max31855 and return it as a big endian integer.
        """

        # read 4 bytes as the size of a message is 32bits
        data = bytes(self.spi.readbytes(4))
        data = int.from_bytes(data, "big", signed=False)
        return data

    def close(self) -> None:
        # close the spi device
        self.spi.close()
