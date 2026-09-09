-- 对话线程归属表：Redis checkpoint 本身不记录所有者
CREATE TABLE conversations (
    thread_id   VARCHAR(128) NOT NULL PRIMARY KEY COMMENT 'LangGraph thread id',
    user_id     VARCHAR(64)  NOT NULL COMMENT '所有者用户 ID',
    created_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                ON UPDATE CURRENT_TIMESTAMP(3),
    KEY idx_conversations_user (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话线程归属';
