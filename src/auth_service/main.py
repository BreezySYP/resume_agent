"""auth_service — 独立鉴权服务（GitHub OAuth 登录 + 签发 Bearer JWT）。

这是全仓库唯一需要 GITHUB_OAUTH_CLIENT_ID/SECRET、Redis（state）的服务。
登录成功后 302 回前端并在 URL fragment 携带 #access_token=...，
前端解析后存内存，后续请求通过 Authorization: Bearer 头访问各 API。
"""

from auth_router import router as auth_router
from shared.web.app import create_app

app = create_app(
    title="Auth Service",
    description="统一登录与 JWT 签发：GitHub OAuth + 后续微信/支付宝/邮箱登录源。",
    version="0.1.0",
    service_name="auth-service",
    routers=[auth_router],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8016, reload=True, log_config=None)
