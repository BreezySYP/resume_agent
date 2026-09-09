"""共享鉴权：JWT access token 签发/验证、GitHub OAuth、FastAPI 依赖。

auth_service 负责登录签发；各 API 服务负责 Bearer token 验证与授权，
复用同一套用户体系（users / oauth_accounts 表）。
"""
