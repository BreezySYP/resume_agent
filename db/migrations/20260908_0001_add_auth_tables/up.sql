-- 新增鉴权基础表：users / oauth_accounts
-- schema 归 migration 管理；代码层只通过 SQLAlchemy ORM 访问。

CREATE TABLE users (
    id          VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT '用户 ID（uuid hex）',
    email       VARCHAR(255) DEFAULT NULL COMMENT '主邮箱，可为空',
    name        VARCHAR(255) NOT NULL DEFAULT '' COMMENT '显示名',
    avatar_url  VARCHAR(1024) DEFAULT NULL,
    is_admin    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '管理员标记',
    created_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='平台用户';

CREATE TABLE oauth_accounts (
    provider             VARCHAR(32)   NOT NULL COMMENT 'github / wechat / alipay ...',
    provider_account_id  VARCHAR(128)  NOT NULL,
    user_id              VARCHAR(64)   NOT NULL,
    provider_username    VARCHAR(255)  DEFAULT NULL COMMENT 'github login 等',
    email                VARCHAR(255)  DEFAULT NULL,
    name                 VARCHAR(255)  NOT NULL DEFAULT '',
    avatar_url           VARCHAR(1024) DEFAULT NULL,
    created_at           DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at           DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                           ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (provider, provider_account_id),
    KEY idx_oauth_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方 OAuth 账号';
