"""physics_example_project: a small rigid-body simulation sketch.

Each submodule exercises specific pypl behaviours:

- ``kinematics``  -- pure-data structs (SVector3, SQuaternion, SMass)
- ``units``       -- enum + free functions (EUnitSystem, conversions)
- ``force``       -- abstract base + concrete subclasses + VForce variant
- ``particle``    -- abstract base, properties, private state, VParticle variant
- ``world``       -- composition with cpp.* smart pointers
- ``field``       -- generic class Field[T] (PEP-695 syntax)
"""

from physics_example_project.force import (
    ConstantForce,
    FrictionForce,
    IForce,
    SpringForce,
    VForce,
)
from physics_example_project.kinematics import SMass, SQuaternion, SVector3
from physics_example_project.particle import IParticle, PointMass, RigidBody, VParticle
from physics_example_project.units import EUnitSystem, meters_to_feet
from physics_example_project.world import SSimulationConfig, World

__all__ = [
    "ConstantForce",
    "EUnitSystem",
    "FrictionForce",
    "IForce",
    "IParticle",
    "PointMass",
    "RigidBody",
    "SMass",
    "SQuaternion",
    "SSimulationConfig",
    "SVector3",
    "SpringForce",
    "VForce",
    "VParticle",
    "World",
    "meters_to_feet",
]
