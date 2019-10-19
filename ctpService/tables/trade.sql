# 1.0 交易表

DROP TABLE IF EXISTS `t_trade`;
CREATE TABLE `t_trade` (
     `InvestorID` varchar(16) NOT NULL,
     `BrokerID` varchar(16) NOT NULL,
     `ExchangeID` varchar(16) NOT NULL,
     `InstrumentID` varchar(16) NOT NULL,
     `OrderID` varchar(16) NOT NULL,
     `TradeID` varchar(16) NOT NULL,
     `Price` double(16, 4) NOT NULL,
     `Volume` int(11) NOT NULL,
     `Direction` varchar(8) NOT NULL,
     `Offset` varchar(8) NOT NULL,
     `TradingDay` varchar(16) NOT NULL,
     `c_time` datetime NOT NULL,
     `u_time` datetime NOT NULL,
     `extra` text,
     UNIQUE KEY (`InvestorID`, `OrderID`, `TradeID`, `TradingDay`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
