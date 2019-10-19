# -*- coding:utf-8 -*-


class Direction(object):
    # 方向常量
    LONG = '0'       # buy
    SHORT = '1'      # sell


class Offset(object):
    # 开平常量
    OPEN = '0'              # 开仓
    CLOSE = '1'             # 平仓
    CLOSE_TODAY = '3'       # 平今
    CLOSE_YESTERDAY = '4'   # 平昨


class PriceType(object):
    # 价格类型常量
    MARKET_PRICE = '1'      # 限价单
    LIMIT_PRICE = '2'       # 市价单
    FAK = u'FAK'
    FOK = u'FOK'

    accept_type = ['limit', 'market']


class OrderType(object):
    # 定单类型
    BUY = u'buy'         # 买开
    SELL = u'sell'       # 卖平
    SHORT = u'short'     # 卖开
    COVER = u'cover'     # 买平

    accept_type = ['buy', 'sell', 'short', 'cover']
