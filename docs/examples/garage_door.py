import dataclasses
import typing
from enum import Enum, auto

from automat import NoTransition, TypeMachineBuilder


class Direction(Enum):
    up = auto()
    stopped = auto()
    down = auto()


@dataclasses.dataclass
class Motor:
    direction: Direction = Direction.stopped

    def up(self) -> None:
        assert self.direction is Direction.stopped
        self.direction = Direction.up
        print("motor running up")

    def stop(self) -> None:
        self.direction = Direction.stopped
        print("motor stopped")

    def down(self) -> None:
        assert self.direction is Direction.stopped
        self.direction = Direction.down
        print("motor running down")


@dataclasses.dataclass
class Alarm:
    def beep(self) -> None:
        "Sound an alarm so that the user can hear."
        print("beep beep beep")


# protocol definition
class GarageController(typing.Protocol):
    def push_button(self) -> None:
        "Push the button to open or close the door"

    def open_sensor(self) -> None:
        "The 'open' sensor activated; the door is fully open."

    def close_sensor(self) -> None:
        "The 'close' sensor activated; the door is fully closed."


# end protocol definition
# core definition
@dataclasses.dataclass
class DoorDevices:
    motor: Motor
    alarm: Alarm


"end core definition"

# end core definition

# start building
builder = TypeMachineBuilder(GarageController, DoorDevices)
# build states
closed = builder.state("closed")
opening = builder.state("opening")
opened = builder.state("opened")
closing = builder.state("closing")
# end states

# build methods
@closed.upon(GarageController.push_button).to(opening)
def start_opening(controller: GarageController, devices: DoorDevices) -> None:
    devices.motor.up()


@opening.upon(GarageController.open_sensor).to(opened)
def finished_opening(controller: GarageController, devices: DoorDevices):
    devices.motor.stop()


@opened.upon(GarageController.push_button).to(closing)
def start_closing(controller: GarageController, devices: DoorDevices) -> None:
    devices.alarm.beep()
    devices.motor.down()


@closing.upon(GarageController.close_sensor).to(closed)
def finished_closing(controller: GarageController, devices: DoorDevices):
    devices.motor.stop()
    # end methods

# do build
machine_factory = builder.build()
# end building
# story
if __name__ == '__main__':
    machine = machine_factory(DoorDevices(Motor(), Alarm()))
    machine.push_button()
    try:
        machine.push_button()
    except NoTransition:
        print("this is not implemented yet")
    machine.open_sensor()
    machine.push_button()
    machine.close_sensor()

# end story
