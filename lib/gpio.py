from typing import Protocol


class GPIOBase(Protocol):

    def setup_pin(self, pin: int, output: bool) -> None:
        ...

    def set_pin(self, pin: int, set_on: bool) -> None:
        ...

    def get_pin(self, pin: int) -> bool:
        ...