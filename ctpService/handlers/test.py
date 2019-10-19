import time

from concurrent.futures import ThreadPoolExecutor  # `pip install futures` for python2
from tornado import web, gen
from tornado.concurrent import run_on_executor
from tornado.iostream import StreamClosedError
from logger import logger

MAX_WORKERS = 4


class TestHandler(web.RequestHandler):
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    @run_on_executor
    def background_task(self):
        """ This will be executed in `executor` pool. """
        time.sleep(1)
        return unicode(time.time())

    @gen.coroutine
    def get(self):
        try:
            while not self._finished:
                now = yield self.background_task()
                yield self.publish(now)
        except Exception as exp:
            logger.error('catch exception {}.'.format(exp))
            raise web.HTTPError(500)
        finally:
            self.finish()

    @gen.coroutine
    def publish(self, message):
        """Pushes data to a listener."""
        try:
            self.write('data: {}\n\n'.format(message))
            yield self.flush()
        except StreamClosedError:
            self._finished = True

    def on_connection_close(self):
        logger.info('>>>>>>>>>>>>>into on_connection_close')

    def on_finish(self):
        logger.info('>>>>>>>>>>>>>into on_finish')
