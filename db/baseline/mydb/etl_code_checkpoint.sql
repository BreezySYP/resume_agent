CREATE TABLE `etl_code_checkpoint` (
  `code` varchar(20) NOT NULL,
  `step` varchar(50) NOT NULL,
  `start_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`code`,`step`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
