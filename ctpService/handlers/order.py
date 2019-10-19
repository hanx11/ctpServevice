# -*- coding:utf-8 -*-

import json
import time
import traceback

import redis
from tornado import escape
from tornado import web, gen
from tornado.iostream import StreamClosedError

from gateway.constant import *
from gateway.trader import NewTrader
from logger import logger
from settings import ORDER_QUEUE_KEY, TRADE_QUEUE_KEY

client = redis.Redis(host='localhost', port=6379)


class SendOrderHandler(web.RequestHandler):

    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.set_header('Connection', 'keep-alive')
        self.body = escape.json_decode(self.request.body)

        user_id = str(self.body.get('user_id'))
        password = str(self.body.get('password'))
        broker_id = str(self.body.get('broker_id', '9999'))
        address = str(self.body.get('address', 'tcp://180.168.146.187:10003'))
        self.trader = NewTrader(user_id, password, broker_id, address)
        self.trader.start()
        # self.db_conn = pymysql.connect(
        #     host=db_config['host'], user=db_config['user'],
        #     password=db_config['passwd'], db=db_config['db'],
        #     charset='utf8', cursorclass=pymysql.cursors.DictCursor
        # )
        # self.cursor = self.db_conn.cursor()

    @gen.coroutine
    def post(self, *args, **kwargs):
        symbol = str(self.body.get('symbol'))
        price = float(self.body.get('price'))
        volume = int(self.body.get('volume'))
        price_type = str(self.body.get('price_type'))
        order_type = str(self.body.get('order_type'))
        trade_date = self.body.get('trade_date', '')

        if price_type not in PriceType.accept_type:
            # 检查可接受的价格类型
            msg = {'code': 4000, 'msg': u'price_type should be [limit|market]'}
            self.write(json.dumps(msg))
            self.finish()

        if order_type not in OrderType.accept_type:
            # 检查可接受的订单类型
            msg = {'code': 4000, 'msg': u'order_type should be [buy|sell|short|cover].'}
            self.write(json.dumps(msg))
            self.finish()

        try:
            yield gen.sleep(0.1)
            self.trader.send_order(symbol, price, volume, price_type, order_type, trade_date=trade_date)
            while not self._finished:
                result = self.trader.get_order_message()
                if result is None:
                    logger.info('order queue is empty!')
                    yield gen.sleep(0.01)
                    continue

                result = json.loads(result)
                if result.get('msg_type') == 'onErrRtnOrderInsert':
                    logger.info('callback onErrRtnOrderInsert: %s', result['data'])
                    # 报单失败
                    self.write('{}\n\n'.format(json.dumps(result['data'])))
                    self.finish()
                elif result.get('msg_type') == 'onRspOrderInsert':
                    # 报单发生错误
                    logger.info('callback onRspOrderInsert: %s', result['data'])
                    self.write(json.dumps(result['data']))
                    self.finish()
                elif result.get('msg_type') == 'onRtnOrder':
                    logger.info('callback onRtnOrder: %s', result['data'])
                    if result['data'].get('OrderStatus') == '5':
                        # 报单被撤销
                        self.write('{}\n\n'.format(json.dumps(result['data'])))
                        self.finish()

                    # 报单成功，插入缓冲队列
                    client.lpush(ORDER_QUEUE_KEY, json.dumps(result['data']))
                    yield self.publish(json.dumps(result['data']))
                elif result.get('msg_type') == 'onRtnTrade':
                    logger.info('callback onRtnTrade: %s', result['data'])
                    # 报单成交，插入交易缓冲队列
                    client.lpush(TRADE_QUEUE_KEY, json.dumps(result['data']))
                    yield self.publish(json.dumps(result['data']))
        except Exception as exp:
            logger.error('catch exception %s', exp)
            logger.error('traceback: %s', traceback.print_exc())
            raise web.HTTPError(500)
        finally:
            if self.trader.connecting:
                self.trader.close()
                logger.info('finally close trader connection!')

    @gen.coroutine
    def publish(self, message):
        """Pushes data to client."""
        try:
            self.write('{}\n\n'.format(message))
            yield self.flush()
        except StreamClosedError:
            self._finished = True

    def on_connection_close(self):
        logger.info('>>>>>>>>>>>>>on_connection_close time: %s', time.time())
        self._finished = True
        if self.trader.connecting:
            self.trader.close()

    def on_finish(self):
        logger.info('<<<<<<<<<<<<<on_finish time: %s', time.time())
        self._finished = True
        if self.trader.connecting:
            self.trader.close()


class CalcelOrderHandler(web.RequestHandler):

    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.set_header('Connection', 'keep-alive')
        self.body = escape.json_decode(self.request.body)

        user_id = str(self.body.get('user_id'))
        password = str(self.body.get('password'))
        broker_id = str(self.body.get('broker_id', '9999'))
        address = str(self.body.get('address', 'tcp://180.168.146.187:10003'))
        self.trader = NewTrader(user_id, password, broker_id, address)
        self.trader.start()

    def post(self, *args, **kwargs):
        symbol = self.body.get('symbol')
        exchange_id = self.body.get('exchange')
        order_id = self.body.get('order_id')
        front_id = self.body.get('front_id')
        session_id = self.body.get('session_id')
        investor_id = self.body.get('user_id')
        broker_id = self.body.get('broker_id')

        if (symbol is None or exchange_id is None or order_id is None or front_id is None
                or session_id is None or investor_id is None or broker_id is None):
            resp = {'code': 4000, 'msg': 'Params error!'}
            self.write(json.dumps(resp))
            self.finish()

        try:
            yield gen.sleep(0.1)
            self.trader.cancel_order(investor_id, broker_id, front_id, session_id, exchange_id, symbol, order_id)
            while not self._finished:
                result = self.trader.get_order_message()
                if result is None:
                    yield gen.sleep(0.01)
                    continue

                data = json.loads(result)
                if data.get('callback') == 'onErrRtnOrderAction':
                    self.write(json.dumps(data))
                    self.finish()
                if data.get('callback') == 'onRspOrderAction':
                    self.write(json.dumps(data))
                    self.finish()
        except Exception as exp:
            logger.error('catch exception %s', exp)
            logger.error('traceback: %s.', traceback.print_exc())
        finally:
            if self.trader.connecting:
                self.trader.close()

    def on_connection_close(self):
        logger.info('>>>>>>>>>> into on_connection_close!')
        self._finished = True
        if self.trader.connecting:
            self.trader.close()

    def on_finish(self):
        logger.info('<<<<<<<<<< into on_finish!')
        self._finished = True
        if self.trader.connecting:
            self.trader.close()
