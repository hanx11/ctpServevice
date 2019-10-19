# -*- coding:utf-8 -*-

from tornado import web
from datetime import datetime


class HelloHandler(web.RequestHandler):

    def get(self, *args, **kwargs):
        self.write('hello, now is {}'.format(datetime.now()))
