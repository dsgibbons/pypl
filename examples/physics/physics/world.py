"""World: top-level simulation container exercising cpp.* smart pointers.

This module also exercises the wider value-type vocabulary (datetime, Path),
``Final[T]`` -> ``const T``, ``@cpp.const`` / ``@cpp.final`` decorators, and
unsigned integer width inference from ``Field(ge=, le=)``.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, Field, PrivateAttr

from physics.force import IForce
from physics.particle import IParticle
from physics.units import EUnitSystem
from pypl import cpp


class SSimulationConfig(BaseModel):
    """Pure-data config record. Should render as a frozen struct."""

    model_config = {"frozen": True}

    dt: float
    max_steps: Annotated[int, Field(ge=0, le=65535)]  # -> std::uint16_t
    unit_system: EUnitSystem
    started_at: datetime | None = None
    recording_path: Path | None = None


@cpp.final
class World(BaseModel):
    """Holds particles (unique ownership) and forces (shared).

    Marked ``cpp.final`` -> rendered with the ``<<final>>`` stereotype.
    ``max_history`` uses ``Final[int]`` -> ``const int``. ``_step_count``
    uses ``cpp.u64`` -> ``std::uint64_t``.
    """

    model_config = {"arbitrary_types_allowed": True}

    max_history: Final[int] = 1024

    _config: SSimulationConfig = PrivateAttr()
    _particles: list[cpp.Unique[IParticle]] = PrivateAttr(default_factory=list)
    _forces: list[cpp.Shared[IForce]] = PrivateAttr(default_factory=list)
    _parent: cpp.Weak[World] | None = PrivateAttr(default=None)
    _focus_particle: cpp.Raw[IParticle] | None = PrivateAttr(default=None)
    _force_by_name: cpp.OMap[str, IForce] = PrivateAttr(default_factory=dict)
    _frame_history: cpp.Vec[float] = PrivateAttr(default_factory=list)
    _step_count: cpp.u64 = PrivateAttr(default=0)

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

    @cpp.const
    def total_kinetic_energy(self) -> float:
        return sum(p.kinetic_energy() for p in self._particles)

    @cpp.const
    def step_count(self) -> cpp.u64:
        return self._step_count
