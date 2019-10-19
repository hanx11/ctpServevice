# 1.0 订单表

DROP TABLE IF EXISTS `t_order`;
CREATE TABLE `t_order` (
     `InvestorID` varchar(16) NOT NULL,
     `BrokerID` varchar(16) NOT NULL,
     `ExchangeID` varchar(16) NOT NULL,
     `FrontID` varchar(16) NOT NULL,
     `SessionID` varchar(16) NOT NULL,
     `InstrumentID` varchar(16) NOT NULL,
     `OrderID` varchar(16) NOT NULL,
     `Price` double(16, 4) NOT NULL,
     `Volume` int(11) NOT NULL,
     `PriceType` varchar(8) NOT NULL,
     `Direction` varchar(8) NOT NULL,
     `Offset` varchar(8) NOT NULL,
     `TradingDay` varchar(16) NOT NULL,
     `status` varchar(8) NOT NULL,
     `c_time` datetime NOT NULL,
     `u_time` datetime NOT NULL,
     `extra` text,
     UNIQUE KEY (`InvestorID`, `OrderID`, `TradingDay`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
