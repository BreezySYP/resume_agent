# auth_service — 独立鉴权服务

全仓库唯一的登录入口与 JWT 签发方：

- `auth_router.py`：`/api/auth/login/github`、`/api/auth/callback/github`、
  `/api/auth/me`；登录成功后 302 回前端并在 URL fragment 携带
  `#access_token=...`。
- `auth_github.py`：GitHub OAuth2 细节（授权 URL / code 换 token / 拉用户）。
- `auth_tokens.py`：JWT access token 签发（各 API 服务只验证，不签发）。
- `main.py`：FastAPI 入口。

模块按**扁平风格**组织（同 stock_agent / stock_etl）：启动时以本目录为
working directory，`uvicorn main:app` 即可，不需要把 auth_service 作为包安装。

## 配置

只此服务需要 `GITHUB_OAUTH_CLIENT_ID/SECRET`、`AUTH_REDIRECT_URI`、
`AUTH_FRONTEND_ORIGINS` 与 Redis（存 OAuth state）。各 API 服务只需要共享的
`AUTH_SESSION_SECRET` 做 token 验证。

## 启动

```bash
cd src/auth_service
uv run uvicorn main:app --host 0.0.0.0 --port 8014 --reload
```

验证：`curl http://localhost:8014/api/auth/login/github?next=/dashboard`
应 307 跳转 GitHub 授权页。

## 登录流程

1. 前端引导浏览器访问 `GET /api/auth/login/github?next=/dashboard`。
2. GitHub 授权后回跳本服务 `/api/auth/callback/github?code=...&state=...`。
3. 服务换 token、upsert 用户，302 到
   `{AUTH_FRONTEND_ORIGINS[0]}/dashboard#access_token=<JWT>`。
4. 前端解析 fragment 存入内存，之后对任意 API 服务请求带
   `Authorization: Bearer <token>`。
