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
| `AUTH_SESSION_SECRET` | auth_service + 所有 API 服务 | JWT 签名密钥，建议 `openssl rand -base64 48` |
| `AUTH_SESSION_DAYS` | auth_service | access token 有效期（默认 7 天） |
| `AUTH_FRONTEND_ORIGINS` | 仅 auth_service | 登录成功跳回的前端白名单（JSON 数组） |
| `AUTH_ADMIN_GITHUB_LOGINS` | 仅 auth_service | 逗号分隔，命中者登录后自动 `is_admin=1` |

## 登录流程（浏览器）

1. 前端引导用户跳转 `GET {auth_service}/api/auth/login/github?next=/dashboard`。
2. auth_service 302 到 GitHub 授权页；GitHub 回跳 auth_service
   `GET /api/auth/callback/github?code=...&state=...`。
3. auth_service 换 token、拉用户、upsert `users/oauth_accounts`，
   然后 **302 回前端**（`AUTH_FRONTEND_ORIGINS` 白名单内），
   跳转 URL 带 `#access_token=<JWT>`。
4. 前端从 `location.hash` 解析 access token，存进内存状态管理（如 Recoil），
   后续请求统一带 `Authorization: Bearer <token>`。

`state` 用一次性随机值存 Redis（10 分钟有效），防止 CSRF 登录。

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
| auth_service `GET /api/auth/me` | 需登录（可用于前端校验 token 是否有效） |
| `/`、`/docs`、`/metrics`、`/health` | 开放（docs 可查看，调接口仍需登录） |

## 注意事项

- 新服务接入：加 `shared` 依赖即可，配置同一个 `AUTH_SESSION_SECRET`，
  业务路由挂 `Depends(get_current_user)` / 授权依赖——不需要 auth router。
- SSE：`EventSource` 不支持自定义 header。前端可用 fetch + ReadableStream
  消费 SSE 并带 Authorization 头，或后续为 SSE 单独定义 token 传递方案。
- Swagger：/docs 页面右上角 Authorize 输入 Bearer token 即可调试
  （token 可先手动登录一次 auth_service 后从地址栏 fragment 复制）。
- access token 是自包含 JWT：服务端不存储、不主动吊销；`exp` 到期自动失效。
- 生产环境 auth_service 与 API 服务如果跨域，仅需 CORS 允许前端 origin；
  没有 cookie，不需要 SameSite/Domain/credentials 配置。
