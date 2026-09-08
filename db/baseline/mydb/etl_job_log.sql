CREATE TABLE `etl_job_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(20) NOT NULL COMMENT '单股触发时填股票代码，全量触发时为 ALL',
  `step` varchar(50) NOT NULL COMMENT 'pipeline step 名称',
  `status` enum('pending','running','success','failed') NOT NULL DEFAULT 'pending',
  `triggered_by` enum('manual','schedule','all') NOT NULL DEFAULT 'manual',
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `row_count` int NOT NULL DEFAULT '0',
  `error_msg` text,
  PRIMARY KEY (`id`),
  KEY `idx_code_step` (`code`,`step`),
  KEY `idx_status` (`status`),
  KEY `idx_started` (`started_at`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='ETL 任务执行日志';
