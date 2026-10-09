CREATE TABLE `t1` (
  `id` int NOT NULL,
  `note` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_note` (`note`(20))
) ENGINE=InnoDB;
CREATE TABLE `t2` (`id` int NOT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB;
