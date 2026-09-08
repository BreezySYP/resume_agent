CREATE TABLE `capital_flow` (
  `code` text,
  `date` date DEFAULT NULL,
  `main_net_inflow` double DEFAULT NULL,
  `large_net_inflow` double DEFAULT NULL,
  `change_pct` double DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
