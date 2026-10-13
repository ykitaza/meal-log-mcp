"""リポジトリの実装（PC 用）。メモリーに置くので、再起動すると消える。"""

import time

from domain.authorization_code import AuthorizationCode
from domain.authorization_request import AuthorizationRequest
from domain.refresh_token import RefreshTokenFamily


class _Expiring:
    def __init__(self):
        self.items = {}

    def put(self, key, value, ttl_seconds):
        self.items[key] = (value, time.time() + ttl_seconds)

    def get(self, key):
        value, expires_at = self.items.get(key, (None, 0))
        return value if expires_at > time.time() else None

    def pop(self, key):
        value, expires_at = self.items.pop(key, (None, 0))
        return value if expires_at > time.time() else None


class MemoryAuthorizationRequestRepository:
    def __init__(self):
        self.store = _Expiring()

    async def save(self, request: AuthorizationRequest, ttl_seconds: int) -> None:
        self.store.put(request.id, request, ttl_seconds)

    async def get(self, request_id: str) -> AuthorizationRequest | None:
        return self.store.get(request_id)


class MemoryAuthorizationCodeRepository:
    def __init__(self):
        self.store = _Expiring()

    async def save(self, code: AuthorizationCode, ttl_seconds: int) -> None:
        self.store.put(code.value, code, ttl_seconds)

    async def take(self, value: str) -> AuthorizationCode | None:
        return self.store.pop(value)


class MemoryRefreshTokenFamilyRepository:
    def __init__(self):
        self.store = _Expiring()

    async def save(self, family: RefreshTokenFamily, ttl_seconds: int) -> None:
        self.store.put(family.id, family, ttl_seconds)

    async def get(self, family_id: str) -> RefreshTokenFamily | None:
        return self.store.get(family_id)

    async def delete(self, family_id: str) -> None:
        self.store.pop(family_id)
