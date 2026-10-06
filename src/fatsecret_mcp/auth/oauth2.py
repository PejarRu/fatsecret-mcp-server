import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class SingleUserOAuthProvider(OAuthAuthorizationServerProvider):
    def __init__(self, issuer_url: str, password: str, data_dir: str = "/app/data"):
        self.issuer_url = issuer_url.rstrip("/")
        self.password = password
        self.path = Path(data_dir) / "mcp_oauth.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clients = {}
        self.pending = {}
        self.codes = {}
        self.access_tokens = {}
        self.refresh_tokens = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.clients = {
            key: OAuthClientInformationFull.model_validate(value)
            for key, value in raw.get("clients", {}).items()
        }
        self.access_tokens = {
            key: AccessToken.model_validate(value)
            for key, value in raw.get("access_tokens", {}).items()
        }
        self.refresh_tokens = {
            key: RefreshToken.model_validate(value)
            for key, value in raw.get("refresh_tokens", {}).items()
        }

    def _save(self):
        payload = {
            "clients": {key: value.model_dump(mode="json") for key, value in self.clients.items()},
            "access_tokens": {key: value.model_dump(mode="json") for key, value in self.access_tokens.items()},
            "refresh_tokens": {key: value.model_dump(mode="json") for key, value in self.refresh_tokens.items()},
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        client_info.client_id = client_info.client_id or secrets.token_urlsafe(24)
        if client_info.token_endpoint_auth_method != "none":
            client_info.client_secret = client_info.client_secret or secrets.token_urlsafe(32)
        client_info.client_id_issued_at = int(time.time())
        self.clients[client_info.client_id] = client_info
        self._save()

    async def authorize(self, client, params: AuthorizationParams):
        request_id = secrets.token_urlsafe(32)
        self.pending[request_id] = (client.client_id, params, time.time() + 600)
        return f"{self.issuer_url}/consent?{urlencode({'request': request_id})}"

    def approve(self, request_id, password):
        pending = self.pending.pop(request_id, None)
        if not pending or pending[2] < time.time() or not secrets.compare_digest(password, self.password):
            return None
        client_id, params, _ = pending
        code_value = secrets.token_urlsafe(32)
        code = AuthorizationCode(
            code=code_value,
            scopes=params.scopes or ["fatsecret:read", "fatsecret:write"],
            expires_at=time.time() + 300,
            client_id=client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject="owner",
        )
        self.codes[code_value] = code
        query = {"code": code_value}
        if params.state:
            query["state"] = params.state
        return f"{params.redirect_uri}?{urlencode(query)}"

    async def load_authorization_code(self, client, authorization_code):
        code = self.codes.get(authorization_code)
        if code and code.client_id == client.client_id and code.expires_at >= time.time():
            return code
        return None

    async def exchange_authorization_code(self, client, authorization_code):
        self.codes.pop(authorization_code.code, None)
        access = secrets.token_urlsafe(48)
        refresh = secrets.token_urlsafe(48)
        expires_at = int(time.time()) + 3600
        self.access_tokens[access] = AccessToken(
            token=access, client_id=client.client_id, scopes=authorization_code.scopes,
            expires_at=expires_at, resource=authorization_code.resource, subject="owner"
        )
        self.refresh_tokens[refresh] = RefreshToken(
            token=refresh, client_id=client.client_id, scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 2592000, resource=authorization_code.resource, subject="owner"
        )
        self._save()
        return OAuthToken(access_token=access, expires_in=3600, scope=" ".join(authorization_code.scopes), refresh_token=refresh)

    async def load_refresh_token(self, client, refresh_token):
        token = self.refresh_tokens.get(refresh_token)
        if token and token.client_id == client.client_id and (not token.expires_at or token.expires_at >= time.time()):
            return token
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        self.refresh_tokens.pop(refresh_token.token, None)
        access = secrets.token_urlsafe(48)
        new_refresh = secrets.token_urlsafe(48)
        granted = scopes or refresh_token.scopes
        self.access_tokens[access] = AccessToken(
            token=access, client_id=client.client_id, scopes=granted, expires_at=int(time.time()) + 3600,
            resource=refresh_token.resource, subject="owner"
        )
        self.refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh, client_id=client.client_id, scopes=granted, expires_at=int(time.time()) + 2592000,
            resource=refresh_token.resource, subject="owner"
        )
        self._save()
        return OAuthToken(access_token=access, expires_in=3600, scope=" ".join(granted), refresh_token=new_refresh)

    async def load_access_token(self, token):
        access = self.access_tokens.get(token)
        if access and (not access.expires_at or access.expires_at >= time.time()):
            return access
        return None

    async def revoke_token(self, token):
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)
        self._save()
