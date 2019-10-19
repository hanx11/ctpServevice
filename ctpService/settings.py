# -*- coding:utf-8 -*-

import os

import db
import tornado
from tornado.options import define, options
from datetime import datetime

from logger import logger

define('port', 10080, help="run on the given port", type=int)
define("debug", default=False, help="debug mode")
define("config", default=None, help="tornado config file")

tornado.options.parse_command_line()


class DeploymentType(object):
    PRODUCTION = "PRODUCTION"
    DEV = "DEV"
    SOLO = "SOLO"
    STAGING = "STAGING"


if 'DEPLOYMENT_TYPE' in os.environ:
    DEPLOYMENT = os.environ['DEPLOYMENT_TYPE'].upper()
else:
    DEPLOYMENT = DeploymentType.SOLO

db_config = {
    'passwd': 'infochannel',
    'user': 'root',
    'host': 'localhost',
    'db': 'fxctp',
    'max_idle': 5 * 60,
}


def init_db():
    db.setup(db_config, minconn=2, maxconn=6, adapter='mysql', key='default', slave=False)
    logger.info('init database')


settings = dict()
settings['rabbitmq_host'] = '192.168.2.194'
settings['debug'] = DEPLOYMENT != DeploymentType.PRODUCTION or options.debug

ORDER_QUEUE_KEY = 'ORDER_QUEUE_{}'.format(datetime.today().strftime('%Y%m%d'))
TRADE_QUEUE_KEY = 'TRADE_QUEUE_{}'.format(datetime.today().strftime('%Y%m%d'))
