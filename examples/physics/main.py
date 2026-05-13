"""Multi-instance entry point for the dynamic-trace mode."""

from physics.force import ConstantForce, SpringForce
from physics.kinematics import SMass, SVector3
from physics.particle import PointMass
from physics.units import EUnitSystem
from physics.world import SSimulationConfig, World


def make_world() -> World:
    config = SSimulationConfig(dt=0.01, max_steps=100, unit_system=EUnitSystem.eSI)
    world = World()
    world._config = config
    return world


def make_point(name: str, x: float, vx: float) -> PointMass:
    p = PointMass(name=name)
    p._position = SVector3(x=x, y=0.0, z=0.0)
    p._velocity = SVector3(x=vx, y=0.0, z=0.0)
    p._mass = SMass(kilograms=1.0)
    return p


def main() -> None:
    world = make_world()
    a = make_point("a", 0.0, 1.0)
    b = make_point("b", 5.0, -0.5)
    world.add_particle(a)
    world.add_particle(b)

    gravity = ConstantForce(direction=SVector3(x=0.0, y=-1.0, z=0.0), magnitude=9.81)
    spring = SpringForce(
        anchor=SVector3(x=0.0, y=0.0, z=0.0),
        stiffness=10.0,
        rest_length=1.0,
    )
    world.add_force("gravity", gravity)
    world.add_force("spring", spring)

    for _ in range(3):
        world.step()

    print("a.kinetic_energy:", a.kinetic_energy())
    print("b.kinetic_energy:", b.kinetic_energy())
    print("world.total_kinetic_energy:", world.total_kinetic_energy())


if __name__ == "__main__":
    main()
