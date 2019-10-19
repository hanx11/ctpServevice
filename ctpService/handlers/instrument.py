# -*- coding:utf-8 -*-

import json
from datetime import datetime

import redis
from tornado import web


class InstrumentListHandler(web.RequestHandler):

    def initialize(self):
        self.redis = redis.Redis(host='localhost', port=6379)

    def get(self, *args, **kwargs):
        instrument_key = 'Instrument-{}'.format(datetime.today().strftime('%Y%m%d'))
        result = []
        for k, v in self.redis.hgetall(instrument_key).items():
            result.append(json.loads(v))

        self.write(json.dumps(result))
