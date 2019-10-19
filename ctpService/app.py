# -*- coding:utf-8 -*-

import db
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import options

from logger import logger
from settings import settings, db_config
from urls import url_patterns


class CtpApplication(web.Application):
    def __init__(self):
        super(CtpApplication, self).__init__(url_patterns, **settings)
        db.setup(db_config, minconn=2, maxconn=5)


def main():
    app = CtpApplication()
    server = HTTPServer(app)
    server.listen(options.port)
    logger.info('CtpServer listen port %s', options.port)
    IOLoop.current().start()


if __name__ == '__main__':
    main()
