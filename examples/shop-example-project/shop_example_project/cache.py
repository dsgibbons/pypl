"""Generic class exercising PEP-695 type parameter syntax."""


class Cache[T]:
    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def store(self, key: str, value: T) -> None:
        self._store[key] = value

    def get(self, key: str) -> T | None:
        return self._store.get(key)


class MyOptions:
    """Deliberately mis-prefixed: all-public should be S-prefixed but isn't."""

    timeout_ms: int = 100
    verbose: bool = False


class IFakeAbstract:
    """Deliberately mis-prefixed: name suggests abstract but no abstract methods."""

    value: int = 0


class SShopWithSecrets:
    """Deliberately mis-prefixed: S-prefix but contains a private member."""

    name: str = ""
    _secret_key: str = ""
