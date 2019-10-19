# -*- coding:utf-8 -*-

import json
import pymssql

from tornado import web

from logger import logger


class OneMinuteBarHandler(web.RequestHandler):

    def initialize(self):
        self.db = pymssql.connect(server='192.168.2.195', user='hanzq', password='infochannel')
        self.cursor = self.db.cursor()

    def get(self, *args, **kwargs):
        exchange = self.get_argument('exchange')
        symbol = self.get_argument('symbol')
        limit = self.get_argument('limit', 100)
        table_name = '{}.dbo.{}_{}_{}'.format(exchange, exchange, 'Min01', symbol)
        sql = "SELECT * FROM {} ORDER BY Date DESC OFFSET 0 ROWS FETCH NEXT {} ROWS ONLY;"
        sql = sql.format(table_name, limit)
        logger.info(sql)
        self.cursor.execute(sql)
        fields = ('DateTime', 'OpenPrice', 'HighPrice', 'LowPrice', 'ClosePrice', 'AveragePrice', 'Amount', 'Hold')
        rows = self.cursor.fetchall()
        rows = [[row[0].strftime('%Y-%m-%d %H:%M:%S'),
                 float(row[1]), float(row[2]), float(row[3]), float(row[4]),
                 int(row[5]), int(row[6]), int(row[7])] for row in rows]
        results = [dict(zip(fields, row)) for row in rows]
        results.sort(key=lambda item: item['DateTime'])
        # sorted(results, key=lambda item: item['DateTime'])
        self.write(json.dumps(results))


class ThirtyMinuteBarHandler(web.RequestHandler):

    def initialize(self):
        self.db = pymssql.connect(server='192.168.2.195', user='hanzq', password='infochannel')
        self.cursor = self.db.cursor()

    def get(self, *args, **kwargs):
        exchange = self.get_argument('exchange')
        symbol = self.get_argument('symbol')
        limit = self.get_argument('limit', 100)
        table_name = '{}.dbo.{}_{}_{}'.format(exchange, exchange, 'Min30', symbol)
        sql = "SELECT * FROM {} ORDER BY Date DESC OFFSET 0 ROWS FETCH NEXT {} ROWS ONLY;"
        sql = sql.format(table_name, limit)
        logger.info(sql)
        self.cursor.execute(sql)
        fields = ('DateTime', 'OpenPrice', 'HighPrice', 'LowPrice', 'ClosePrice', 'Amount', 'Hold')
        rows = self.cursor.fetchall()
        rows = [[row[0].strftime('%Y-%m-%d %H:%M:%S'), float(row[1]), float(row[2]), float(row[3]), float(row[4]),
                 int(row[5]), int(row[6])] for row in rows]
        results = [dict(zip(fields, row)) for row in rows]
        results.sort(key=lambda item: item['DateTime'])
        self.write(json.dumps(results))


class DailyBarHandler(web.RequestHandler):

    def initialize(self):
        self.db = pymssql.connect(server='192.168.2.195', user='hanzq', password='infochannel')
        self.cursor = self.db.cursor()

    def get(self, *args, **kwargs):
        exchange = self.get_argument('exchange')
        symbol = self.get_argument('symbol')
        limit = self.get_argument('limit', 100)
        table_name = '{}.dbo.{}_{}_{}'.format(exchange, exchange, 'Day', symbol)
        sql = "SELECT * FROM {} ORDER BY Date DESC OFFSET 0 ROWS FETCH NEXT {} ROWS ONLY;"
        sql = sql.format(table_name, limit)
        logger.info(sql)
        self.cursor.execute(sql)
        fields = ('DateTime', 'OpenPrice', 'HighPrice', 'LowPrice', 'ClosePrice', 'Amount', 'Hold')
        rows = self.cursor.fetchall()
        rows = [[row[0].strftime('%Y-%m-%d %H:%M:%S'), float(row[1]), float(row[2]), float(row[3]), float(row[4]),
                 int(row[5]), int(row[6])] for row in rows]
        results = [dict(zip(fields, row)) for row in rows]
        results.sort(key=lambda item: item['DateTime'])
        self.write(json.dumps(results))
