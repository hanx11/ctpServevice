# -*- coding:utf-8 -*-

import json
from Queue import Empty

from tornado import web, gen
from tornado.iostream import StreamClosedError

from gateway.trader import NewTrader
from logger import logger


class AccountHandler(web.RequestHandler):

    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.set_header('Connection', 'keep-alive')
        user_id = str(self.get_argument('user_id'))
        password = str(self.get_argument('password'))
        broker_id = str(self.get_argument('broker_id', '9999'))
        address = str(self.get_argument('address', 'tcp://180.168.146.187:10003'))
        logger.info('address: %s', address)
        self.trader = NewTrader(user_id, password, broker_id, address)
        self.trader.start()

    @gen.coroutine
    def get(self, *args, **kwargs):
        try:
            while not self._finished:
                yield gen.sleep(1)
                self.trader.query_account()
                try:
                    msg = self.trader.get_account()
                    msg = json.loads(msg)
                    account = json.dumps(msg['data'])
                    yield self.publish(account)
                except Empty:
                    continue
        except Exception as exp:
            logger.error('catch exception {}.'.format(exp))
            raise web.HTTPError(500)
        finally:
            if self.trader.connecting:
                self.trader.close()
                logger.info('finally close trader connection!')

    @gen.coroutine
    def publish(self, message):
        """Pushes data to a listener."""
        try:
            self.write('{}\n\n'.format(message))
            yield self.flush()
        except StreamClosedError:
            self._finished = True

    def on_connection_close(self):
        logger.info('>>>>>>>>>>>>>into on_connection_close')
        self._finished = True
        if self.trader.connecting:
            self.trader.close()

    def on_finish(self):
        logger.info('>>>>>>>>>>>>>into on_finish')
        self._finished = True
        if self.trader.connecting:
            self.trader.close()
