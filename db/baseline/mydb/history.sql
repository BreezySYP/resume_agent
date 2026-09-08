CREATE TABLE `history` (
  `date` datetime DEFAULT NULL,
  `open` double DEFAULT NULL,
  `close` double DEFAULT NULL,
  `high` double DEFAULT NULL,
  `low` double DEFAULT NULL,
  `volume` double DEFAULT NULL,
  `code` varchar(10) DEFAULT NULL,
  `name` text,
  `price_change` double DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code_date` (`code`,`date`)
) ENGINE=InnoDB AUTO_INCREMENT=3780993 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
