# -*- coding:utf-8 -*-

import sys
import time

from trader import Trader


def main():
    price = sys.argv[1]
    order_type = sys.argv[2]
    symbol = 'zn1901'
    volume = 1
    price_type = 'limit'
    user_id = '126077'
    password = 'hanfeng911'
    broker_id = '9999'
    address = 'tcp://180.168.146.187:10003'
    trader = Trader(user_id, password, broker_id, address)
    trader.connect()
    time.sleep(0.1)
    trader.send_order(symbol, price, volume, price_type, order_type)
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
