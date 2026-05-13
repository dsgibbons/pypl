"""World: top-level simulation container exercising cpp.* smart pointers."""

from pydantic import BaseModel, PrivateAttr

from physics_example_project.force import IForce
from physics_example_project.particle import IParticle
from physics_example_project.units import EUnitSystem
from pypl import cpp


class SSimulationConfig(BaseModel):
    """Pure-data config record. Should render as a frozen struct."""

    model_config = {"frozen": True}

    dt: float
    max_steps: int
    unit_system: EUnitSystem


class World(BaseModel):
    """Holds particles (unique ownership) and forces (shared)."""

    model_config = {"arbitrary_types_allowed": True}

    _config: SSimulationConfig = PrivateAttr()
    _particles: list[cpp.Unique[IParticle]] = PrivateAttr(default_factory=list)
    _forces: list[cpp.Shared[IForce]] = PrivateAttr(default_factory=list)
    _parent: cpp.Weak[World] | None = PrivateAttr(default=None)
    _focus_particle: cpp.Raw[IParticle] | None = PrivateAttr(default=None)
    _force_by_name: cpp.OMap[str, IForce] = PrivateAttr(default_factory=dict)
    _frame_history: cpp.Vec[float] = PrivateAttr(default_factory=list)
    _step_count: int = PrivateAttr(default=0)

    def step(self) -> None:
        self._step_count += 1
        for particle in self._particles:
            particle.integrate(self._config.dt)
        self._frame_history.append(self._config.dt * self._step_count)

    def add_particle(self, particle: cpp.Unique[IParticle]) -> None:
        self._particles.append(particle)

    def add_force(self, name: str, force: cpp.Shared[IForce]) -> None:
        self._forces.append(force)
        self._force_by_name[name] = force

    def total_kinetic_energy(self) -> float:
        return sum(p.kinetic_energy() for p in self._particles)
