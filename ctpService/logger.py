# -*- coding:utf-8 -*-

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(threadName)s %(levelname)s || %(asctime)s || %(message)s'
)
logger = logging.getLogger('ctpServer')
