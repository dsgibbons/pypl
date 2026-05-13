"""Particle hierarchy: abstract base with private state + property getters/setters."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, PrivateAttr

from physics.kinematics import SMass, SQuaternion, SVector3


class IParticle(BaseModel, ABC):
    _position: SVector3 = PrivateAttr()
    _velocity: SVector3 = PrivateAttr()
    _mass: SMass = PrivateAttr()

    @abstractmethod
    def integrate(self, dt: float) -> None: ...

    @property
    def position(self) -> SVector3:
        return self._position

    @position.setter
    def position(self, value: SVector3) -> None:
        self._position = value

    @property
    def velocity(self) -> SVector3:
        return self._velocity

    def kinetic_energy(self) -> float:
        v = self._velocity
        speed_sq = v.x * v.x + v.y * v.y + v.z * v.z
        return 0.5 * self._mass.kilograms * speed_sq


class PointMass(IParticle):
    name: str

    def integrate(self, dt: float) -> None:
        p = self._position
        v = self._velocity
        self._position = SVector3(x=p.x + v.x * dt, y=p.y + v.y * dt, z=p.z + v.z * dt)


class RigidBody(IParticle):
    _orientation: SQuaternion = PrivateAttr()
    name: str

    def integrate(self, dt: float) -> None:
        p = self._position
        v = self._velocity
        self._position = SVector3(x=p.x + v.x * dt, y=p.y + v.y * dt, z=p.z + v.z * dt)


VParticle = PointMass | RigidBody
