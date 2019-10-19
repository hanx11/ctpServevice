# -*- coding:utf-8 -*-

import json

from tornado import websocket

from gateway.trader import Trader
from logger import logger


class BrokerHandler(websocket.WebSocketHandler):

    def open(self, *args, **kwargs):
        self.trader = Trader(self.push_message)
        self.trader.start()

    def on_message(self, message):
        msg = json.loads(message)
        if msg['method'] == 'connect':
            logger.info('connect %s', msg)
            user_id = str(msg['data']['user_id'])
            password = str(msg['data']['password'])
            broker_id = str(msg['data']['broker_id'])
            address = str(msg['data']['address'])
            if self.trader.connecting is False:
                self.trader.connect(user_id, password, broker_id, address)

        if msg['method'] == 'query_account':
            self.trader.query_account()
            logger.info('query account.')

        if msg['method'] == 'query_position':
            self.trader.query_position()
            logger.info('query position.')

        if msg['method'] == 'send_order':
            data = msg['data']
            self.trader.send_order(data)

    def push_message(self, message):
        if self.ws_connection:
            self.write_message(message)

    def on_connection_close(self):
        logger.info('on_connection_close invoked!')
        if self.trader.connecting:
            self.trader.close()

    def on_close(self):
        logger.info('on_close invoked!')
        if self.trader.connecting:
            self.trader.close()
