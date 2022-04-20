from typing import Protocol


class MAX31855SPI(Protocol):

    def read(self) -> int:
        ...

    def close(self) -> None:
        ...
