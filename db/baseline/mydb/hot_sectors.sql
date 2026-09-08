CREATE TABLE `hot_sectors` (
  `date` date NOT NULL,
  `sector_code` varchar(20) NOT NULL,
  `sector_name` varchar(100) NOT NULL,
  `sector_type` varchar(20) DEFAULT 'concept',
  `change_pct` double DEFAULT NULL,
  `index_value` double DEFAULT NULL,
  `turnover_rate` double DEFAULT NULL,
  `net_inflow` double DEFAULT NULL,
  `leading_stock_name` varchar(100) DEFAULT NULL,
  `leading_stock_code` varchar(20) DEFAULT NULL,
  `sector_rank` int DEFAULT NULL,
  `attention_score` double DEFAULT NULL,
  `top_stocks` text,
  `fetch_time` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`date`,`sector_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
