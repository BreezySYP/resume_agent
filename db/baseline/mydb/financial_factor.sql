CREATE TABLE `financial_factor` (
  `code` text,
  `name` text,
  `report_date` datetime DEFAULT NULL,
  `profitability_score` double DEFAULT NULL,
  `growth_score` double DEFAULT NULL,
  `quality_score` double DEFAULT NULL,
  `safety_score` double DEFAULT NULL,
  `total_financial_score` double DEFAULT NULL,
  `total_financial_rank` double DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
