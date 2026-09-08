CREATE TABLE `etl_checkpoint` (
  `step` varchar(50) NOT NULL,
  `start_date` date DEFAULT NULL,
  `start_code` varchar(20) DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_completed_date` date DEFAULT NULL,
  `last_completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`step`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
