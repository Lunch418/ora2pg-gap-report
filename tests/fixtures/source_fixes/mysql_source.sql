CREATE TABLE `orders` (
  `id` int NOT NULL,
  `status` enum('new','paid','shipped') NOT NULL DEFAULT 'new',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
