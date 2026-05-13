"""Generic scalar/vector field. Exercises PEP-695 type parameter syntax."""


class Field[T]:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._cells: dict[tuple[int, int], T] = {}

    def set(self, x: int, y: int, value: T) -> None:
        self._cells[(x, y)] = value

    def get(self, x: int, y: int) -> T | None:
        return self._cells.get((x, y))

    def size(self) -> int:
        return self._width * self._height
