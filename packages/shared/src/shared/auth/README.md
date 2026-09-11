# 共享鉴权（JWT Bearer token）

鉴权拆成两部分：

- **auth_service**（`src/auth_service`，唯一入口）：GitHub OAuth 登录 + 签发 JWT
  access token。以后扩展微信/支付宝/邮箱登录源时，只改这一个服务。
  OAuth 与签发代码全部在 auth_service 目录内（`auth_router.py` /
  `auth_github.py` / `auth_tokens.py`），不进 shared 包。
- **各 API 服务**（stock_agent / stock_dashboard / 未来新增服务）：只负责验证
  `Authorization: Bearer <token>`，不挂 auth router、不配 OAuth client 密钥。

`packages/shared/src/shared/auth/` 只保留各服务都要用的部分：

| 文件 | 用途 |
| --- | --- |
| `token.py` | `decode_access_token`：验签名/过期/typ（签发在 auth_service/tokens.py） |
| `deps.py` | `get_current_user`（Bearer → 用户）+ 各授权依赖（admin/self/read） |
| `errors.py` | 401/403/404 领域异常 + FastAPI 全局映射 |
| `context.py` | contextvar 当前用户工具 |
| `users.py` / `models.py` | 用户/oauth_accounts 表访问与 ORM 声明 |

用户体系：MySQL `users` + `oauth_accounts` 表，表结构由 `db/migrations/` 管理
（代码不做建表，只用 SQLAlchemy ORM 访问）。

权限（403）：**FastAPI 路由依赖**做授权判断，如 `require_admin`、`require_self_or_admin`、
`require_conversation_owner_or_admin`、`require_read_or_admin`，挂在路由的
`dependencies=[Depends(...)]` 上；handler 内不出现 user 参数与手写 403/404。

认证（401）：`get_current_user` 从 Authorization 头解析 Bearer JWT、校验签名与过期、
加载用户并写入 contextvar（`shared/auth/context.py`，仅作工具，后台任务不依赖它）。

错误：service/依赖层抛 `UnauthorizedError` / `PermissionDeniedError` / `NotFoundError`，
`create_app` 全局映射为 401/403/404。

## 配置

见仓库根 `.env.example` 的 `# Auth` 段：

| 环境变量 | 谁需要 | 说明 |
| --- | --- | --- |
| `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` | 仅 auth_service | GitHub OAuth App |
| `AUTH_REDIRECT_URI` | 仅 auth_service | auth_service 回调地址，需与 GitHub OAuth App 一致 |
| `AUTH_JWT_PUBLIC_KEY_B64` | 各 API 服务 | RS256 验签公钥（base64 PEM），离线验签、无网络请求 |
| `AUTH_SESSION_DAYS` | auth_service | access token 有效期（默认 7 天） |

> **shared 里没有、也不允许有私钥配置。** `AUTH_JWT_PRIVATE_KEY_B64` /
> `AUTH_JWT_KEY_ID` / `AUTH_LOGIN_CODE_TTL` 定义在 `src/auth_service/auth_config.py`，
> 只属于 auth_service；`tests/shared/test_settings.py` 有守卫测试防止它们回流到 shared。

### 验签公钥

```bash
openssl pkey -pubout -in jwt_private.pem | base64 -w0   # 填 AUTH_JWT_PUBLIC_KEY_B64
```

各服务把公钥放进自己的 env 即可离线验签：**没有网络请求、没有缓存、也不依赖
auth_service 在线**。代价是轮换密钥时需要把新公钥重新分发到各服务并重启。
| `AUTH_FRONTEND_ORIGINS` | 仅 auth_service | 登录成功跳回的前端白名单（JSON 数组） |
| `AUTH_CLIENT_CREDENTIALS` | 仅 auth_service | 程序化调用凭证（JSON 数组），见下方 |
| `AUTH_ADMIN_GITHUB_LOGINS` | 仅 auth_service | 逗号分隔，命中者登录后自动 `is_admin=1` |

## 登录流程（浏览器）

1. 前端引导用户跳转 `GET {auth_service}/api/auth/login/github?next=/dashboard`。
2. auth_service 302 到 GitHub 授权页；GitHub 回跳 auth_service
   `GET /api/auth/callback/github?code=...&state=...`。
3. auth_service 换 token、拉用户、upsert `users/oauth_accounts`，
   生成**一次性 code**（60 秒、单次使用，存 Redis），
   **302 回前端**（`AUTH_FRONTEND_ORIGINS` 白名单内）并带上 `?code=...`。
4. 前端用 code 调 `POST /api/auth/token`：

   ```bash
   curl -X POST http://localhost:8016/api/auth/token \
     -H "Content-Type: application/json" \
     -d '{"grant_type": "authorization_code", "code": "<回调里的 code>"}'
   ```

   JWT 在**响应体**里返回，不经过 URL——不会进地址栏、浏览器历史或访问日志。
5. 前端把 token 存进内存状态管理（如 Recoil），后续请求统一带
   `Authorization: Bearer <token>`。

### 为什么用 code 而不是直接把 token 放 URL

URL（无论 query 还是 fragment）会留在浏览器历史、Referer 和各类日志里，
token 一旦泄漏就是长期有效凭证。code 则：

- **一次性**：兑换后立刻从 Redis 删除，重放直接 400；
- **短时效**：默认 60 秒；
- 即使泄漏，没有 code 之外的凭证也无法单独使用。

`state` 用一次性随机值存 Redis（10 分钟有效），防止 CSRF 登录。

## 程序化调用（Swagger / 后台服务 / 脚本）

### 个人 API key（推荐，给人用）

登录后由 UI 调 `POST /api/auth/tokens` 生成自己的 API key（明文只返回一次，
之后只显示前缀），行为类似 Tavily/DeepSeek 的 key：

```bash
# 需带登录得到的 Bearer token
curl -X POST http://localhost:8014/api/auth/tokens \
  -H "Authorization: Bearer <login-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "我的脚本", "expires_days": 90, "admin": false}'

# 列出 / 撤销
curl http://localhost:8014/api/auth/tokens -H "Authorization: Bearer <login-jwt>"
curl -X DELETE http://localhost:8014/api/auth/tokens/<id> -H "Authorization: Bearer <login-jwt>"
```

要点：

- 明文形如 `pat_xxxxx`，只存哈希（`personal_access_tokens.token_hash`）；
- **权限上限由服务端强制**：普通用户即使传 `admin: true` 也只能拿到普通 token；
- `admin` 权限在创建时固化，之后用户角色变化不影响已签发 token；
- 撤销、过期立即生效（每次请求查库）；`expires_days` 不填则不过期。

### 服务凭证（client credentials，系统内部调用）

没有用户归属的定时任务/内部服务，可用 client credentials 换 service token：

```bash
curl -X POST http://localhost:8014/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "dashboard", "client_secret": "..."}'
```

返回 `{"access_token": "<jwt>", "token_type": "bearer", ...}`，token 的
`typ=service`。API 服务验证时直接采用 token 声明的身份（`sub`/`admin`），
不查 users 表——适合后台任务与 service-to-service 调用。

`AUTH_CLIENT_CREDENTIALS` 配置示例：

```json
[{"client_id": "dashboard", "client_secret": "xxx", "sub": "u1", "admin": true}]
```

- `sub`：该 client 代表哪个身份（可填真实 user_id，或 `client:dashboard` 这类标识）；
- `admin: true`：签发管理员 service token；
- `days`：POST 时可选覆盖有效期（1–30 天）。

## Swagger 调试

所有挂 `get_current_user`/`require_*` 依赖的路由会自动声明 HTTPBearer，
Swagger 页面右上角出现 **Authorize** 按钮：

1. 打开任意服务 `/docs`；
2. 点 Authorize，粘贴上面换到的 token（或浏览器登录后 fragment 里的 token）；
3. Try it out 的请求会自动带 `Authorization: Bearer`。

auth_service 自身的 `/api/auth/login/github`、`/api/auth/token` 不需要
Authorize（前者是跳转入口，后者用 client_id/client_secret 换取凭证）。

## 权限映射

| 服务/接口 | 权限 |
| --- | --- |
| stock_agent `/api/ai/users/{user_id}/memories` | `require_self_or_admin`：本人或 admin |
| stock_agent `/api/ai/threads/{id}/conversation`、DELETE | `require_conversation_owner_or_admin`：owner 或 admin（他人非 admin → 404） |
| stock_agent `/api/ai/qa`（触发）| `require_conversation_claim`：新线程/owner/admin 可触发；他人线程非 admin → 403；写记忆用登录 user_id |
| stock_agent `/api/ai/qa/stream/{job_id}`（SSE）| 登录 |
| stock_agent `/api/ai/faithfulness` | `require_admin` |
| stock_dashboard `/api/stocks*` GET/HEAD | `require_read_or_admin`：登录即可 |
| stock_dashboard `/api/stocks*` 写/改方法 | `require_read_or_admin`：仅 admin |
| stock_dashboard `/api/etl*`、`/api/status*` | `require_admin`（router 级） |
| auth_service `GET /api/auth/me`、`/api/auth/tokens*` | 需 Bearer（登录用户或 API key）；API key 生成/列表/撤销仅本人 |
| auth_service `POST /api/auth/token` | client credentials，无需登录（系统内部调用） |
| `/`、`/docs`、`/metrics`、`/health` | 开放（docs 可查看，调接口仍需登录） |

## 注意事项

- **RS256 非对称签名**：auth_service 用私钥签发，其他服务用
  `AUTH_JWT_PUBLIC_KEY_B64` 离线验签，**任何业务服务都无法伪造 token**——
  这是相对共享密钥（HS256）的核心改进。
- 新服务接入：加 `shared` 依赖、配 `AUTH_JWT_PUBLIC_KEY_B64`，业务路由挂
  `Depends(get_current_user)` / 授权依赖——不需要 auth router，也不需要密钥。
- 密钥轮换：换私钥后重新分发公钥到各服务并重启；
  所有已签发 token 会立即失效，用户需重新登录。
- SSE：`EventSource` 不支持自定义 header。前端可用 fetch + ReadableStream
  消费 SSE 并带 Authorization 头，或后续为 SSE 单独定义 token 传递方案。
- Swagger：/docs 页面右上角 Authorize 输入 Bearer token 即可调试
  （token 可用 `POST /api/auth/token` 换取，或用 UI 生成的 API key）。
- access token 是自包含 JWT：服务端不存储、不主动吊销；`exp` 到期自动失效。
- 生产环境 auth_service 与 API 服务如果跨域，仅需 CORS 允许前端 origin；
  没有 cookie，不需要 SameSite/Domain/credentials 配置。
