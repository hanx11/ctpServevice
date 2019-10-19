# -*- coding:utf-8 -*-

import logging
import threading
import time
from Queue import Queue, Empty
from datetime import datetime

import redis

from constant import *
from gateway import CtpTdApi

logging.basicConfig(
    level=logging.DEBUG,
    format='%(threadName)s %(levelname)s || %(asctime)s || %(message)s'
)


class NewTrader(threading.Thread):

    def __init__(self, user_id, password, broker_id, address):
        super(NewTrader, self).__init__()
        self.user_id = user_id
        self.password = password
        self.broker_id = broker_id
        self.address = address

        self.queue = Queue()
        self.td_api = CtpTdApi(user_id, password, broker_id, address, self.queue)
        self.redis = redis.Redis(host='localhost', port=6379)
        self.order_id_key = 'UNIQUE_ORDER_ID'
        self.connect_time = None
        self.running = False

    def connect(self):
        self.connecting = True
        self.connect_time = datetime.now().strftime('%H:%M:%S')
        logging.info('trader connect_time: %s', self.connect_time)
        self.td_api.connect()

    def close(self):
        self.connecting = False
        self.td_api.close()
        self.running = False

    def start(self):
        super(NewTrader, self).start()
        self.connect()
        self.running = True

    def run(self):
        while self.running:
            time.sleep(1)

    @property
    def order_id(self):
        """
        :return:
        """
        return self.redis.lpop(self.order_id_key)

    def send_order(self, symbol, price, volume, price_type, order_type, trade_date=None):
        """
        发单
        :param symbol:
        :param price:
        :param volume:
        :param price_type: limit or market
        :param order_type:
        :param trade_date: 上期所订单平仓时需要，决定平今或平昨
        :return:
        """
        today_str = datetime.today().strftime('%Y%m%d')
        logging.info('trade_date = %s', trade_date)
        exchange_id = self.redis.hget('SymbolExchangeMap', symbol)
        logging.info('in send_order exchange_id = %s', exchange_id)
        if price_type == 'market':
            order_price_type = PriceType.MARKET_PRICE
        else:
            order_price_type = PriceType.LIMIT_PRICE

        direction, offset = Direction.LONG, Offset.OPEN
        if order_type == OrderType.BUY:
            direction = Direction.LONG
            offset = Offset.OPEN
        elif order_type == OrderType.SELL:
            direction = Direction.SHORT
            offset = Offset.CLOSE
        elif order_type == OrderType.SHORT:
            direction = Direction.SHORT
            offset = Offset.OPEN
        elif order_type == OrderType.COVER:
            direction = Direction.LONG
            offset = Offset.CLOSE

        if exchange_id == 'SHFE' and order_type in (OrderType.SELL, OrderType.COVER) and today_str == trade_date:
            # 上期所平今
            offset = Offset.CLOSE_TODAY
        if exchange_id == 'SHFE' and order_type in (OrderType.SELL, OrderType.COVER) and today_str > trade_date:
            # 上期所平昨
            offset = Offset.CLOSE_YESTERDAY

        order = {
            'InstrumentID': symbol,
            'LimitPrice': float(price),
            'VolumeTotalOriginal': int(volume),
            'OrderPriceType': order_price_type,
            'OrderRef': self.order_id,
            'Direction': direction,
            'CombOffsetFlag': offset,
            'InvestorID': self.user_id,
            'UserID': self.user_id,
            'BrokerID': self.broker_id,
            'CombHedgeFlag': '1',  # 投机单
            'ContingentCondition': '1',  # 立即发单
            'ForceCloseReason': '0',  # 非强平
            'IsAutoSuspend': 0,  # 非自动挂起
            'TimeCondition': '3',  # 当日有效
            'VolumeCondition': '1',  # 任何数量
            'MinVolume': 1,  # 最小成交量为1
        }

        # if order_type in [OrderType.BUY, OrderType.COVER]:
        #     order['OrderRef'] = self.order_id

        if price_type == 'FAK':
            order['OrderPriceType'] = '2'  # 限价
            order['TimeCondition'] = '1'  # 立即完成，否则撤销
            order['VolumeCondition'] = '1'  # 任何数量
        if price_type == 'FOK':
            order['OrderPriceType'] = '2'  # 限价
            order['TimeCondition'] = '1'  # 立即完成，否则撤销
            order['VolumeCondition'] = '3'  # 全部数量

        self.td_api.sendOrder(order)

    def get_order_message(self):
        try:
            msg = self.queue.get(block=False)
            return msg
        except Empty:
            return None

    def query_account(self):
        logging.info('query_account time: %s', time.time())
        self.td_api.qryAccount()

    def query_position(self):
        logging.info('query_position time: %s', time.time())
        self.td_api.qryPosition()

    def get_account(self):
        return self.queue.get(block=False)

    def get_position(self):
        return self.queue.get(block=False)

    def cancel_order(self, investor_id, broker_id, front_id, session_id, exchange_id, symbol, order_id):
        """
        :param investor_id:
        :param broker_id:
        :param front_id:
        :param session_id:
        :param exchange_id:
        :param symbol:
        :param order_id:
        :return:
        """
        req = dict()
        req['InstrumentID'] = symbol
        req['ExchangeID'] = exchange_id
        req['OrderRef'] = order_id
        req['FrontID'] = front_id
        req['SessionID'] = session_id

        req['ActionFlag'] = '0'
        req['BrokerID'] = broker_id
        req['InvestorID'] = investor_id
        self.td_api.cancelOrder(req)


class Trader(threading.Thread):

    def __init__(self, callback):
        self.user_id = None
        self.password = None
        self.broker_id = None
        self.address = None
        self.td_api = None
        self.queue = Queue()
        self.running = False
        self.connecting = False
        self.order_id_key = 'UNIQUE_ORDER_ID'
        self.cache = redis.Redis(host='localhost', port=6379)
        self.callback = callback
        super(Trader, self).__init__()

    def connect(self, user_id, password, broker_id, address):
        self.user_id = user_id
        self.password = password
        self.broker_id = broker_id
        self.address = address
        self.td_api = CtpTdApi(user_id, password, broker_id, address, self.queue)
        self.td_api.connect()
        self.connecting = True

    def run(self):
        while self.running:
            try:
                msg = self.queue.get(block=False)
                self.callback(msg)
            except Empty:
                time.sleep(0.01)

    def start(self):
        self.running = True
        super(Trader, self).start()

    def close(self):
        self.connecting = False
        self.td_api.close()
        self.running = False

    def query_account(self):
        self.td_api.qryAccount()

    def query_position(self):
        self.td_api.qryPosition()

    @property
    def order_id(self):
        """
        :return:
        """
        return self.cache.lpop(self.order_id_key)

    def send_order(self, data):
        """
        发单
        :param data: dict
        :return:
        """
        symbol = data['symbol']
        price = data['price']
        volume = data['volume']
        price_type = data['price_type']
        order_type = data['order_type']
        trade_date = data.get('trade_date', None)

        today_str = datetime.today().strftime('%Y%m%d')
        logging.info('trade_date = %s', trade_date)
        exchange_id = self.cache.hget('SymbolExchangeMap', symbol)
        logging.info('in send_order exchange_id = %s', exchange_id)
        if price_type == 'market':
            order_price_type = PriceType.MARKET_PRICE
        else:
            order_price_type = PriceType.LIMIT_PRICE

        direction, offset = Direction.LONG, Offset.OPEN
        if order_type == OrderType.BUY:
            direction = Direction.LONG
            offset = Offset.OPEN
        elif order_type == OrderType.SELL:
            direction = Direction.SHORT
            offset = Offset.CLOSE
        elif order_type == OrderType.SHORT:
            direction = Direction.SHORT
            offset = Offset.OPEN
        elif order_type == OrderType.COVER:
            direction = Direction.LONG
            offset = Offset.CLOSE

        if exchange_id == 'SHFE' and order_type in (OrderType.SELL, OrderType.COVER) and today_str == trade_date:
            # 上期所平今
            offset = Offset.CLOSE_TODAY
        if exchange_id == 'SHFE' and order_type in (OrderType.SELL, OrderType.COVER) and today_str > trade_date:
            # 上期所平昨
            offset = Offset.CLOSE_YESTERDAY

        order = {
            'InstrumentID': symbol,
            'LimitPrice': float(price),
            'VolumeTotalOriginal': int(volume),
            'OrderPriceType': order_price_type,
            'OrderRef': self.order_id,
            'Direction': direction,
            'CombOffsetFlag': offset,
            'InvestorID': self.user_id,
            'UserID': self.user_id,
            'BrokerID': self.broker_id,
            'CombHedgeFlag': '1',  # 投机单
            'ContingentCondition': '1',  # 立即发单
            'ForceCloseReason': '0',  # 非强平
            'IsAutoSuspend': 0,  # 非自动挂起
            'TimeCondition': '3',  # 当日有效
            'VolumeCondition': '1',  # 任何数量
            'MinVolume': 1,  # 最小成交量为1
        }

        # if order_type in [OrderType.BUY, OrderType.COVER]:
        #     order['OrderRef'] = self.order_id

        if price_type == 'FAK':
            order['OrderPriceType'] = '2'  # 限价
            order['TimeCondition'] = '1'  # 立即完成，否则撤销
            order['VolumeCondition'] = '1'  # 任何数量
        if price_type == 'FOK':
            order['OrderPriceType'] = '2'  # 限价
            order['TimeCondition'] = '1'  # 立即完成，否则撤销
            order['VolumeCondition'] = '3'  # 全部数量

        self.td_api.sendOrder(order)
