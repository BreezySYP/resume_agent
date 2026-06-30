    CREATE TABLE IF NOT EXISTS etl_job_log (
        id           BIGINT AUTO_INCREMENT PRIMARY KEY,
        code         VARCHAR(20)  NOT NULL COMMENT '单股触发时填股票代码，全量触发时为 ALL',
        step         VARCHAR(50)  NOT NULL COMMENT 'pipeline step 名称',
        status       ENUM('pending','running','success','failed') NOT NULL DEFAULT 'pending',
        triggered_by ENUM('manual','schedule','all') NOT NULL DEFAULT 'manual',
        started_at   DATETIME     NULL,
        finished_at  DATETIME     NULL,
        duration_ms  INT          NULL,
        row_count    INT          NOT NULL DEFAULT 0,
        error_msg    TEXT         NULL,
        INDEX idx_code_step (code, step),
        INDEX idx_status    (status),
        INDEX idx_started   (started_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETL 任务执行日志'