from lib.gpio import GPIOBase


class MAX31855SPIBitBang:
    def __init__(
            self,
            gpio: GPIOBase,
            cs_pin: int,
            clock_pin: int,
            data_pin: int
    ) -> None:
        """
        Initialize Soft (Bitbang) SPI bus

        Parameters:
        - cs_pin:    Chip Select (CS) / Slave Select (SS) pin (Any GPIO)
        - clock_pin: Clock (SCLK / SCK) pin (Any GPIO)
        - data_pin:  Data input (SO / MOSI) pin (Any GPIO)
        """
        self.gpio = gpio
        self.cs_pin = cs_pin
        self.clock_pin = clock_pin
        self.data_pin = data_pin

        # Initialize GPIO
        self.gpio.setup_pin(self.cs_pin, True)
        self.gpio.setup_pin(self.clock_pin, True)
        self.gpio.setup_pin(self.data_pin, False)

        # Pull chip select high to make chip inactive
        self.gpio.set_pin(self.cs_pin, True)

    def read(self) -> int:
        bytesin = 0

        # Select the chip
        self.gpio.set_pin(self.cs_pin, False)

        # Read in 32 bits
        for i in range(32):
            self.gpio.set_pin(self.clock_pin, False)
            bytesin <<= 1
            if self.gpio.get_pin(self.data_pin):
                bytesin |= 1
            self.gpio.set_pin(self.clock_pin, True)

        # Unselect the chip
        self.gpio.set_pin(self.cs_pin, True)

        return bytesin

    def close(self) -> None:
        """Selective GPIO cleanup"""
        self.gpio.setup_pin(self.cs_pin, False)
        self.gpio.setup_pin(self.clock_pin, False)
