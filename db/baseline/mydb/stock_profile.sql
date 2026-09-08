CREATE TABLE `stock_profile` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(10) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `business` text,
  `scope` text,
  `update_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=34337 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
