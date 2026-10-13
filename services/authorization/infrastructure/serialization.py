"""集約を保存できる形（dict）に変換する。リポジトリの実装だけが使う。"""

from domain.authorization_code import AuthorizationCode
from domain.authorization_request import AuthorizationRequest, Status
from domain.refresh_token import RefreshTokenFamily
from domain.values import ClientId, CodeChallenge, RedirectUri, ResourceIndicator, Scope, Subject


def _subject_to_dict(subject: Subject | None) -> dict | None:
    return None if subject is None else {"id": subject.id, "email": subject.email}


def _subject_from_dict(d: dict | None) -> Subject | None:
    return None if d is None else Subject(d["id"], d["email"])


def request_to_dict(r: AuthorizationRequest) -> dict:
    return {
        "id": r.id,
        "client_id": r.client_id.value,
        "client_name": r.client_name,
        "redirect_uri": r.redirect_uri.value,
        "client_state": r.client_state,
        "scope": list(r.scope.values),
        "code_challenge": r.code_challenge.value,
        "resource": r.resource.value,
        "status": r.status.value,
        "subject": _subject_to_dict(r.subject),
    }


def request_from_dict(d: dict) -> AuthorizationRequest:
    return AuthorizationRequest(
        id=d["id"],
        client_id=ClientId(d["client_id"]),
        client_name=d["client_name"],
        redirect_uri=RedirectUri(d["redirect_uri"]),
        client_state=d["client_state"],
        scope=Scope(tuple(d["scope"])),
        code_challenge=CodeChallenge(d["code_challenge"]),
        resource=ResourceIndicator(d["resource"]),
        status=Status(d["status"]),
        subject=_subject_from_dict(d["subject"]),
    )


def code_to_dict(c: AuthorizationCode) -> dict:
    return {
        "value": c.value,
        "client_id": c.client_id.value,
        "redirect_uri": c.redirect_uri.value,
        "scope": list(c.scope.values),
        "code_challenge": c.code_challenge.value,
        "resource": c.resource.value,
        "subject": _subject_to_dict(c.subject),
        "expires_at": c.expires_at,
    }


def code_from_dict(d: dict) -> AuthorizationCode:
    return AuthorizationCode(
        value=d["value"],
        client_id=ClientId(d["client_id"]),
        redirect_uri=RedirectUri(d["redirect_uri"]),
        scope=Scope(tuple(d["scope"])),
        code_challenge=CodeChallenge(d["code_challenge"]),
        resource=ResourceIndicator(d["resource"]),
        subject=_subject_from_dict(d["subject"]),
        expires_at=float(d["expires_at"]),
    )


def family_to_dict(f: RefreshTokenFamily) -> dict:
    return {
        "id": f.id,
        "client_id": f.client_id.value,
        "subject": _subject_to_dict(f.subject),
        "scope": list(f.scope.values),
        "resource": f.resource.value,
        "current_hash": f.current_hash,
        "expires_at": f.expires_at,
    }


def family_from_dict(d: dict) -> RefreshTokenFamily:
    return RefreshTokenFamily(
        id=d["id"],
        client_id=ClientId(d["client_id"]),
        subject=_subject_from_dict(d["subject"]),
        scope=Scope(tuple(d["scope"])),
        resource=ResourceIndicator(d["resource"]),
        current_hash=d["current_hash"],
        expires_at=float(d["expires_at"]),
    )
