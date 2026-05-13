"""Force hierarchy: abstract base + concrete forces, plus VForce variant."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from physics.kinematics import SVector3


class IForce(BaseModel, ABC):
    @abstractmethod
    def evaluate(self, position: SVector3, time: float) -> SVector3: ...


class ConstantForce(IForce):
    direction: SVector3
    magnitude: float

    def evaluate(self, position: SVector3, time: float) -> SVector3:
        return SVector3(
            x=self.direction.x * self.magnitude,
            y=self.direction.y * self.magnitude,
            z=self.direction.z * self.magnitude,
        )


class SpringForce(IForce):
    anchor: SVector3
    stiffness: float
    rest_length: float

    def evaluate(self, position: SVector3, time: float) -> SVector3:
        dx = position.x - self.anchor.x
        dy = position.y - self.anchor.y
        dz = position.z - self.anchor.z
        scale = -self.stiffness
        return SVector3(x=dx * scale, y=dy * scale, z=dz * scale)


class FrictionForce(IForce):
    coefficient: float

    def evaluate(self, position: SVector3, time: float) -> SVector3:
        return SVector3(x=0.0, y=0.0, z=0.0)


VForce = ConstantForce | SpringForce | FrictionForce
