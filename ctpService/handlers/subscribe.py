# -*- coding:utf-8 -*-

import uuid
from datetime import datetime

from tornado import web, gen
from tornado.iostream import StreamClosedError

from consumer import TickConsumer
from logger import logger


class SubscribeHandler(web.RequestHandler):

    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.set_header('Connection', 'keep-alive')
        symbol = self.get_argument('symbol')
        date_str = self.get_argument('date', datetime.now().strftime('%Y%m%d'))
        exchange_id = '{}-{}'.format(date_str, symbol)
        queue_name = str(uuid.uuid4())
        self.consumer = TickConsumer(exchange_id, queue_name)
        self.consumer.start()

    @gen.coroutine
    def get(self, *args, **kwargs):
        try:
            while not self._finished:
                message = yield self.consumer.get_message()
                yield self.publish(message)
        except Exception as exp:
            logger.error('catch exception {}.'.format(exp))
            raise web.HTTPError(500)
        finally:
            self.consumer.stop()
            self.finish()

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
        self.consumer.stop()

    def on_finish(self):
        logger.info('>>>>>>>>>>>>>into on_finish')
        self.consumer.stop()
