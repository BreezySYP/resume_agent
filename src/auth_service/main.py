"""auth_service — 独立鉴权服务（GitHub OAuth 登录 + 签发 Bearer JWT）。

这是全仓库唯一需要 GITHUB_OAUTH_CLIENT_ID/SECRET、Redis（state）和
JWT 私钥（RS256）的服务。登录成功后 302 回前端并带上**一次性 code**（非 token），
前端用 code 调 POST /api/auth/token 换取 JWT，token 不会出现在 URL 里。
其他服务用 AUTH_JWT_PUBLIC_KEY_B64 离线验签（无需访问本服务）。
"""

from auth_keys import configure_shared_verification
from auth_router import router as auth_router
from shared.web.app import create_app

# 导入时把派生公钥交给 shared 验签层（shared 只拿到公钥，永远接触不到私钥）
configure_shared_verification()

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
