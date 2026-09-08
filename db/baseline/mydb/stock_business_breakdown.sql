CREATE TABLE `stock_business_breakdown` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(30) DEFAULT NULL,
  `code` varchar(10) DEFAULT NULL,
  `report_date` date DEFAULT NULL,
  `category_type` varchar(50) DEFAULT NULL,
  `category_name` varchar(100) DEFAULT NULL,
  `revenue` double DEFAULT NULL,
  `revenue_ratio` double DEFAULT NULL,
  `cost` double DEFAULT NULL,
  `cost_ratio` double DEFAULT NULL,
  `profit` double DEFAULT NULL,
  `profit_ratio` double DEFAULT NULL,
  `gross_margin` double DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6223983 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
