# -*- coding:utf-8 -*-

from handlers.account import AccountHandler
from handlers.broker import BrokerHandler
from handlers.hello import HelloHandler
from handlers.history import OneMinuteBarHandler, ThirtyMinuteBarHandler, DailyBarHandler
from handlers.instrument import InstrumentListHandler
from handlers.order import SendOrderHandler, CalcelOrderHandler
from handlers.position import PositionHandler
from handlers.subscribe import SubscribeHandler
from handlers.test import TestHandler

url_patterns = [
    (r'/test', TestHandler),
    (r'/hello', HelloHandler),

    (r'/v1/subscribe', SubscribeHandler),
    (r'/v1/account', AccountHandler),
    (r'/v1/position', PositionHandler),
    (r'/v1/send_order', SendOrderHandler),
    (r'/v1/cancel_order', CalcelOrderHandler),
    (r'/v1/instrument_list', InstrumentListHandler),
    (r'/v1/history/one_minute', OneMinuteBarHandler),
    (r'/v1/history/thirty_minute', ThirtyMinuteBarHandler),
    (r'/v1/history/daily', DailyBarHandler),

    (r'/v1/broker', BrokerHandler),
]
