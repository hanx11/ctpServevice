# -*- coding:utf-8 -*-

import json

from tornado import gen
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.websocket import websocket_connect


class Broker(object):

    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.current()
        self.auth = {
            'user_id': '126077',
            'password': 'hanfeng911',
            'broker_id': '9999',
            'address': 'tcp://180.168.146.187:10003',
        }
        self.ws = None
        self.connect()
        PeriodicCallback(self.query_position, self.timeout * 1000).start()
        self.ioloop.start()

    @gen.coroutine
    def connect(self):
        print "trying to connect"
        try:
            self.ws = yield websocket_connect(self.url)
            msg = {
                'method': 'connect',
                'data': self.auth,
            }
            self.ws.write_message(json.dumps(msg))
        except Exception, e:
            print "connection error"
        else:
            print "connected"
            self.run()

    @gen.coroutine
    def run(self):
        while True:
            msg = yield self.ws.read_message()
            print 'receive message: {}'.format(msg)
            if msg is None:
                print "connection closed"
                self.ws = None
                break

    def keep_alive(self):
        if self.ws is None:
            self.connect()
        else:
            self.ws.write_message("keep alive")

    def query_account(self):
        msg = {
            'method': 'query_account',
            'data': self.auth
        }
        self.ws.write_message(json.dumps(msg))

    def query_position(self):
        msg = {
            'method': 'query_position',
            'data': self.auth
        }
        self.ws.write_message(json.dumps(msg))


if __name__ == "__main__":
    client = Broker("ws://192.168.2.194:10080/v1/broker", 2)
