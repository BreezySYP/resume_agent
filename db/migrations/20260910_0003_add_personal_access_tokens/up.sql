-- 新增 personal_access_tokens：用户自助生成的 API key（类似 Tavily/DeepSeek）
-- 明文只在创建时返回一次，库里只存 token_hash；权限在创建时固化在 is_admin 列。

CREATE TABLE personal_access_tokens (
    id           VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT 'token 记录 ID（uuid hex）',
    user_id      VARCHAR(64)  NOT NULL COMMENT '归属用户',
    name         VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注名，如「我的脚本」',
    token_prefix VARCHAR(16)  NOT NULL COMMENT '明文前缀，列表展示用',
    token_hash   CHAR(64)     NOT NULL COMMENT 'sha256(token)，验证用',
    is_admin     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '创建时固化的管理员权限',
    expires_at   DATETIME(3)  DEFAULT NULL COMMENT 'NULL 表示不过期',
    revoked_at   DATETIME(3)  DEFAULT NULL COMMENT '非 NULL 表示已撤销',
    last_used_at DATETIME(3)  DEFAULT NULL COMMENT '最近使用时间',
    created_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                 ON UPDATE CURRENT_TIMESTAMP(3),
    UNIQUE KEY uq_pat_hash (token_hash),
    KEY idx_pat_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户 personal access token';
