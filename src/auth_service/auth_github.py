"""GitHub OAuth2：授权 URL / code 换 token / 拉取用户信息（仅 auth_service 使用）。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from auth_config import get_auth_service_settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"
GITHUB_SCOPES = "read:user user:email"


class GitHubOAuthError(Exception):
    """GitHub OAuth 交换失败。"""


def build_authorize_url(state: str) -> str:
    cfg = get_auth_service_settings()
    params = {
        "client_id": cfg.github_oauth_client_id,
        "redirect_uri": cfg.auth_redirect_uri,
        "scope": GITHUB_SCOPES,
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """用授权码换 access_token。"""
    cfg = get_auth_service_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": cfg.github_oauth_client_id,
                "client_secret": cfg.github_oauth_client_secret,
                "code": code,
                "redirect_uri": cfg.auth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("error") or not data.get("access_token"):
        raise GitHubOAuthError(str(data))
    return str(data["access_token"])


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    """拉取 /user；公开 email 为空时再请求 /user/emails 取主邮箱。"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        user_resp = await client.get(f"{GITHUB_API_URL}/user", headers=headers)
        user_resp.raise_for_status()
        user = user_resp.json()
        if not user.get("email"):
            emails_resp = await client.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
            if emails_resp.is_success:
                primary = next(
                    (e for e in emails_resp.json() if e.get("primary") and e.get("verified")),
                    None,
                )
                if primary:
                    user["email"] = primary.get("email")
    return user


def github_identity(user: dict[str, Any]) -> dict[str, Any]:
    """把 GitHub /user 响应规整为 upsert_oauth_user 所需字段。"""
    return {
        "provider": "github",
        "account_id": str(user.get("id", "")),
        "username": user.get("login"),
        "email": user.get("email"),
        "name": user.get("name") or user.get("login") or "",
        "avatar_url": user.get("avatar_url"),
    }
