CREATE TABLE `technical_factor` (
  `code` varchar(10) DEFAULT NULL,
  `name` varchar(20) DEFAULT NULL,
  `date` datetime DEFAULT NULL,
  `trend_score` double DEFAULT NULL,
  `momentum_score` double DEFAULT NULL,
  `volume_score` double DEFAULT NULL,
  `total_technical_score` double DEFAULT NULL,
  `technical_rank` double DEFAULT NULL,
  KEY `code_date` (`code`,`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
