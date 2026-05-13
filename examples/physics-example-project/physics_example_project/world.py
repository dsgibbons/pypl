"""World: top-level simulation container exercising cpp.* smart pointers."""

from pydantic import BaseModel

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

    _config: SSimulationConfig
    _particles: list[cpp.Unique[IParticle]] = []
    _forces: list[cpp.Shared[IForce]] = []
    _parent: cpp.Weak[World] | None = None
    _focus_particle: cpp.Raw[IParticle] | None = None
    _force_by_name: cpp.OMap[str, IForce] = {}
    _frame_history: cpp.Vec[float] = []
    _step_count: int = 0

    def step(self) -> None:
        self._step_count += 1
        for particle in self._particles:  # type: ignore[union-attr]
            particle.integrate(self._config.dt)
        self._frame_history.append(self._config.dt * self._step_count)  # type: ignore[union-attr]

    def add_particle(self, particle: cpp.Unique[IParticle]) -> None:
        self._particles.append(particle)  # type: ignore[arg-type]

    def add_force(self, name: str, force: cpp.Shared[IForce]) -> None:
        self._forces.append(force)  # type: ignore[arg-type]
        self._force_by_name[name] = force  # type: ignore[index]

    def total_kinetic_energy(self) -> float:
        return sum(p.kinetic_energy() for p in self._particles)  # type: ignore[union-attr]
