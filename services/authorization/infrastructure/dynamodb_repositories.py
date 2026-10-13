"""リポジトリの実装（Lambda 用）。Lambda は呼ばれるたびに別の実行環境になることがあるので、DynamoDB に置く。

1つのテーブルに、種類（request / code / refresh）とキーをつないだ pk で保存する。
expires_at を過ぎた項目は DynamoDB の TTL が消す（消えるまで遅れることがあるので、期限は自分でも確かめる）。
boto3 は同期なので、呼び出しをスレッドに逃がして async にする（Lambda ではスレッドが使える）。
"""

import json
import time
from functools import partial

import anyio

from domain.authorization_code import AuthorizationCode
from domain.authorization_request import AuthorizationRequest
from domain.refresh_token import RefreshTokenFamily
from infrastructure.serialization import (
    code_from_dict,
    code_to_dict,
    family_from_dict,
    family_to_dict,
    request_from_dict,
    request_to_dict,
)


class _Table:
    def __init__(self, table_name: str, kind: str):
        import boto3  # Lambda の実行環境に入っている

        self.table = boto3.resource("dynamodb").Table(table_name)
        self.kind = kind

    async def _call(self, method, **kwargs) -> dict:
        return await anyio.to_thread.run_sync(partial(method, **kwargs))

    async def put(self, key: str, data: dict, ttl_seconds: int) -> None:
        await self._call(self.table.put_item, Item={
            "pk": f"{self.kind}#{key}",
            "data": json.dumps(data),
            "expires_at": int(time.time()) + ttl_seconds,
        })

    async def get(self, key: str) -> dict | None:
        return self._alive((await self._call(self.table.get_item, Key={"pk": f"{self.kind}#{key}"})).get("Item"))

    async def pop(self, key: str) -> dict | None:
        # 取り出すと同時に消す
        deleted = await self._call(self.table.delete_item, Key={"pk": f"{self.kind}#{key}"}, ReturnValues="ALL_OLD")
        item = deleted.get("Attributes")
        return self._alive(item)

    @staticmethod
    def _alive(item: dict | None) -> dict | None:
        if item is None or item["expires_at"] <= time.time():
            return None
        return json.loads(item["data"])


class DynamoDBAuthorizationRequestRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name, "request")

    async def save(self, request: AuthorizationRequest, ttl_seconds: int) -> None:
        await self.table.put(request.id, request_to_dict(request), ttl_seconds)

    async def get(self, request_id: str) -> AuthorizationRequest | None:
        data = await self.table.get(request_id)
        return None if data is None else request_from_dict(data)


class DynamoDBAuthorizationCodeRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name, "code")

    async def save(self, code: AuthorizationCode, ttl_seconds: int) -> None:
        await self.table.put(code.value, code_to_dict(code), ttl_seconds)

    async def take(self, value: str) -> AuthorizationCode | None:
        data = await self.table.pop(value)
        return None if data is None else code_from_dict(data)


class DynamoDBRefreshTokenFamilyRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name, "refresh")

    async def save(self, family: RefreshTokenFamily, ttl_seconds: int) -> None:
        await self.table.put(family.id, family_to_dict(family), ttl_seconds)

    async def get(self, family_id: str) -> RefreshTokenFamily | None:
        data = await self.table.get(family_id)
        return None if data is None else family_from_dict(data)

    async def delete(self, family_id: str) -> None:
        await self.table.pop(family_id)
