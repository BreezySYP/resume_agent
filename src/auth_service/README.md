# auth_service — 独立鉴权服务

全仓库唯一的登录入口与 JWT 签发方：

- `auth_router.py`：`/api/auth/login/github`、`/api/auth/callback/github`、
  `/api/auth/token`、`/api/auth/me`；登录成功后 302 回前端并携带**一次性 code**
  （`?code=...`），前端用 code 调 token 端点换 JWT。
- `auth_github.py`：GitHub OAuth2 细节（授权 URL / code 换 token / 拉用户）。
- `auth_keys.py`：RS256 私钥加载与签名、派生公钥（**私钥只在本服务**）。
- `auth_config.py`：本服务私有配置（私钥、GitHub OAuth、登录 code TTL 等），
  **不存在于 shared**——shared 只认验签公钥。
- `auth_tokens.py`：JWT access token 签发（RS256）。
- `main.py`：FastAPI 入口。

另外提供两类程序化凭证：

- `POST/GET/DELETE /api/auth/tokens*`：用户自助生成/管理 personal access token
  （API key，形如 `pat_xxx`，明文只返回一次，权限上限由服务端强制）；
- `POST /api/auth/token`：client credentials 换 service token，供无用户归属的
  系统内部调用/定时任务使用。

模块按**扁平风格**组织（同 stock_agent / stock_etl）：启动时以本目录为
working directory，`uvicorn main:app` 即可，不需要把 auth_service 作为包安装。

## 配置

只此服务需要 `GITHUB_OAUTH_CLIENT_ID/SECRET`、`AUTH_REDIRECT_URI`、
`AUTH_FRONTEND_ORIGINS`、Redis（存 OAuth state / 登录 code）和
`AUTH_JWT_PRIVATE_KEY_B64`（RS256 私钥）。各 API 服务只需用
`AUTH_JWT_PUBLIC_KEY_B64` 离线验签——它们**没有签发 token 的能力**。

私钥派生公钥：

```bash
uv run python -c "import sys; sys.path.insert(0,'src/auth_service'); from auth_keys import public_key_b64; print(public_key_b64())"
```

## 启动

```bash
cd src/auth_service
uv run uvicorn main:app --host 0.0.0.0 --port 8016 --reload
```

验证：`curl http://localhost:8016/api/auth/login/github?next=/dashboard`
应 307 跳转 GitHub 授权页。

## 登录流程

1. 前端引导浏览器访问 `GET /api/auth/login/github?next=/dashboard`。
2. GitHub 授权后回跳本服务 `/api/auth/callback/github?code=...&state=...`。
3. 服务换 GitHub token、upsert 用户，生成**一次性 code**（60 秒、单次使用），
   302 到 `{AUTH_FRONTEND_ORIGINS[0]}/dashboard?code=<code>`。
4. 前端用 code 调 `POST /api/auth/token`
   （`{"grant_type":"authorization_code","code":"..."}`），在**响应体**里拿到 JWT，
   存入内存；token 不出现在 URL、历史记录或日志中。
5. 之后对任意 API 服务请求带 `Authorization: Bearer <token>`。
