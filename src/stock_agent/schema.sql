CREATE TABLE IF NOT EXISTS agent_memories (
    id              VARCHAR(36)  NOT NULL PRIMARY KEY COMMENT '记忆唯一ID (UUID)',
    user_id         VARCHAR(64)  NOT NULL COMMENT '用户ID',
    namespace        VARCHAR(128) NOT NULL COMMENT '命名空间，如 user:{id}:profile',
    memory_type     VARCHAR(32)  NOT NULL COMMENT 'profile / episode / procedural / lesson',
    
    -- 内容
    content         TEXT         NOT NULL COMMENT '记忆正文（已摘要，建议控制长度）',
    content_hash    CHAR(64)     DEFAULT NULL COMMENT '内容hash，用于快速去重',
    
    -- 状态与冲突处理
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' 
                    COMMENT 'active / superseded / conflict / deleted',
    superseded_by   VARCHAR(36)  DEFAULT NULL COMMENT '被哪条新记忆取代',
    confidence      DECIMAL(3,2) DEFAULT 1.00 COMMENT '置信度 0~1',
    importance      TINYINT      DEFAULT 3 COMMENT '重要性 1~5',
    
    -- 来源
    source          VARCHAR(32)  NOT NULL DEFAULT 'agent_inferred'
                    COMMENT 'user_explicit / user_feedback / agent_inferred / system',
    source_thread_id VARCHAR(64) DEFAULT NULL COMMENT '来源会话 thread_id',
    source_job_id   VARCHAR(64)  DEFAULT NULL COMMENT '来源任务 job_id',
    
    -- 向量关联
    qdrant_point_id VARCHAR(36)  DEFAULT NULL COMMENT '对应 Qdrant point id',
    
    -- 可选：完整原文存对象存储时使用
    object_key      VARCHAR(512) DEFAULT NULL COMMENT 'MinIO/S3 对象key（原文）',
    
    -- 时间与过期
    created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) 
                    ON UPDATE CURRENT_TIMESTAMP(3),
    expires_at      DATETIME(3)  DEFAULT NULL COMMENT '过期时间，中期记忆用',
    
    -- 扩展
    metadata        JSON         DEFAULT NULL COMMENT '额外结构化信息',
    
    INDEX idx_user_ns_status (user_id, namespace, status),
    INDEX idx_user_type_status (user_id, memory_type, status),
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_content_hash (content_hash),
    INDEX idx_superseded_by (superseded_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Agent 中长期记忆主表';