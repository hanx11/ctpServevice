# -*- coding:utf-8 -*-

import json
import logging
import os
import random
import time
from datetime import datetime

import redis
from vnctptd import TdApi

logging.basicConfig(
    level=logging.DEBUG,
    format='%(threadName)s %(levelname)s || %(asctime)s || %(message)s'
)

client = redis.Redis(host='localhost', port=6379)


class CtpTdApi(TdApi):
    """CTP交易API实现"""

    def __init__(self, user_id, password, broker_id, address, queue=None):
        """API对象的初始化函数"""
        super(CtpTdApi, self).__init__()

        self.reqID = 0  # 操作请求编号
        self.orderRef = 0  # 订单编号

        self.connectionStatus = False  # 连接状态
        self.loginStatus = False  # 登录状态
        self.authStatus = False  # 验证状态
        self.loginFailed = False  # 登录失败（账号密码错误）

        self.userID = user_id  # 账号
        self.password = password  # 密码
        self.brokerID = broker_id  # 经纪商代码
        self.address = address  # 服务器地址

        self.frontID = 0  # 前置机编号
        self.sessionID = 0  # 会话编号

        self.exchange_id = None   # 本次连接委托单交易所ID
        self.order_sys_id = None  # 本次连接内委托单系统ID

        self.posDict = {}
        self.symbolExchangeDict = {}  # 保存合约代码和交易所的印射关系
        self.symbolSizeDict = {}  # 保存合约代码和合约大小的印射关系

        self.requireAuthentication = False

        self.queue = queue    # 回报消息保存队列

    def connect(self):
        """初始化连接"""
        # 如果尚未建立服务器连接，则进行连接
        if not self.connectionStatus:
            # 创建C++环境中的API对象，这里传入的参数是需要用来保存.con文件的文件夹路径
            path = self.get_temp_path()
            self.createFtdcTraderApi(path)

            # 设置数据同步模式为推送从今日开始所有数据
            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)

            # 注册服务器地址
            self.registerFront(self.address)

            # 初始化连接，成功会调用onFrontConnected
            self.init()
            return

        # 若已经连接但尚未登录，则进行登录
        if self.requireAuthentication and not self.authStatus:
            self.authenticate()

        if not self.loginStatus:
            self.login()

    def onFrontConnected(self):
        """服务器连接"""
        self.connectionStatus = True

        logging.info('Trading server connected.')

        if self.requireAuthentication:
            self.authenticate()
        else:
            self.login()

    def login(self):
        """连接服务器"""
        # 如果之前有过登录失败，则不再进行尝试
        if self.loginFailed:
            return

        # 如果填入了用户名密码等，则登录
        if self.userID and self.password and self.brokerID:
            req = dict()
            req['UserID'] = self.userID
            req['Password'] = self.password
            req['BrokerID'] = self.brokerID
            self.reqID += 1
            self.reqUserLogin(req, self.reqID)

    def onRspUserLogin(self, data, error, n, last):
        """登陆回报"""
        # 如果登录成功，推送日志信息
        if error['ErrorID'] == 0:
            self.frontID = str(data['FrontID'])
            self.sessionID = str(data['SessionID'])
            logging.info('onRspUserLogin frontID = %s', self.frontID)
            logging.info('onRspUserLogin sessionID = %s', self.sessionID)
            self.loginStatus = True

            logging.info('Trading server login completed.')
            # 确认结算信息
            req = {
                'BrokerID': self.brokerID,
                'InvestorID': self.userID,
            }
            self.reqID += 1
            self.reqSettlementInfoConfirm(req, self.reqID)
            # 否则，推送错误信息
        else:
            msg = 'onRspUserLogin ErrorID: %s, ErrorMsg: %s'
            logging.error(msg, error['ErrorID'], error['ErrorMsg'].decode('gbk'))
            # 标识登录失败，防止用错误信息连续重复登录
            self.loginFailed = True

    def authenticate(self):
        """申请验证"""
        if self.userID and self.brokerID and self.authCode and self.userProductInfo:
            req = dict()
            req['UserID'] = self.userID
            req['BrokerID'] = self.brokerID
            req['AuthCode'] = self.authCode
            req['UserProductInfo'] = self.userProductInfo
            self.reqID += 1
            self.reqAuthenticate(req, self.reqID)

    def onRspAuthenticate(self, data, error, n, last):
        """验证客户端回报"""
        if error['ErrorID'] == 0:
            self.authStatus = True
            logging.info('Trading server authenticated.')
            self.login()
        else:
            msg = 'onRspAuthenticate ErrorID: %s, ErrorMsg: %s'
            logging.error(msg, error['ErrorID'], error['ErrorMsg'].decode('gbk'))

    def close(self):
        """关闭"""
        self.exit()

    def onFrontDisconnected(self, n):
        """服务器断开"""
        self.connectionStatus = False
        self.loginStatus = False
        logging.info('Trading server disconnected.')

    def onHeartBeatWarning(self, n):
        logging.warning('heart beat message # %s', n)

    def onRspUserLogout(self, data, error, n, last):
        """登出回报"""
        if error['ErrorID'] == 0:
            self.loginStatus = False
            logging.info('Trading server logout completed.')
        else:
            msg = 'ErrorID: %s, ErrorMsg: %s'
            logging.error(msg, error['ErrorID'], error['ErrorMsg'].decode('gbk'))

    def onRspSettlementInfoConfirm(self, data, error, n, last):
        """确认结算信息回报"""
        logging.info('Settlement info confirmed.')
        logging.info('onRspSettlementInfoConfirm time: %s', time.time())
        logging.info('onRspSettlementInfoConfirm: %s', data)
        # 查询合约代码
        self.reqID += 1
        self.reqQryInstrument({}, self.reqID)

    def onRspQryInstrument(self, data, error, n, last):
        """合约查询回报"""
        symbol = data['InstrumentID']
        exchange_id = data['ExchangeID']
        # logging.info('onRspQryInstrument data: %s', data)
        client.hset('SymbolExchangeMap', symbol, exchange_id)
        self.symbolExchangeDict.update({symbol: exchange_id})
        today_str = datetime.today().strftime('%Y%m%d')
        contract = {
            'InstrumentID': data['InstrumentID'],
            'InstrumentName': data['InstrumentName'].decode('gbk').encode('utf-8'),
            'ExchangeID': data['ExchangeID'],
            'CreateDate': data['CreateDate'],
            'MinBuyVolume': data['MinBuyVolume'],
            'PriceTick': data['PriceTick'],
            'EndDelivDate': data['EndDelivDate'],
            'ProductID': data['ProductID'],
            'OpenDate': data['OpenDate'],
            'PositionType': data['PositionType'],
            'MaxLimitOrderVolume': data['MaxLimitOrderVolume'],
            'VolumeMultiple': data['VolumeMultiple'],
            'ProductClass': data['ProductClass'],
        }
        instrument_info_key = 'Instrument-{}'.format(today_str)
        client.hset(instrument_info_key, symbol, json.dumps(contract))

    def qryAccount(self):
        """查询账户"""
        self.reqID += 1
        self.reqQryTradingAccount({}, self.reqID)

    def onRspQryTradingAccount(self, data, error, n, last):
        """资金账户查询回报"""
        logging.info('onRspQryTradingAccount time: %s', time.time())
        logging.info('data: %s', data)
        balance = (data['PreBalance'] - data['PreCredit'] - data['PreMortgage'] +
                   data['Mortgage'] - data['Withdraw'] + data['Deposit'] +
                   data['CloseProfit'] + data['PositionProfit'] + data['CashIn'] -
                   data['Commission'])
        account = {
            'accountID': data['AccountID'],
            'preBalance': data['PreBalance'],
            'available': data['Available'],
            'commission': data['Commission'],
            'margin': data['CurrMargin'],
            'closeProfit': data['CloseProfit'],
            'positionProfit': data['PositionProfit'],
            'balance': balance,
        }
        logging.info('onRspQryTradingAccount data: %s', account)
        data = {
            'msg_type': 'account',
            'data': account,
        }
        self.queue.put(json.dumps(data))
        # account = VtAccountData()
        # account.gatewayName = self.gatewayName
        #
        # # 账户代码
        # account.accountID = data['AccountID']
        # account.vtAccountID = '.'.join([self.gatewayName, account.accountID])
        #
        # # 数值相关
        # account.preBalance = data['PreBalance']
        # account.available = data['Available']
        # account.commission = data['Commission']
        # account.margin = data['CurrMargin']
        # account.closeProfit = data['CloseProfit']
        # account.positionProfit = data['PositionProfit']
        #
        # # 这里的balance和快期中的账户不确定是否一样，需要测试
        # account.balance = (data['PreBalance'] - data['PreCredit'] - data['PreMortgage'] +
        #                    data['Mortgage'] - data['Withdraw'] + data['Deposit'] +
        #                    data['CloseProfit'] + data['PositionProfit'] + data['CashIn'] -
        #                    data['Commission'])
        #
        # # 推送
        # self.gateway.onAccount(account)

    def qryPosition(self):
        """查询持仓"""
        self.reqID += 1
        req = {
            'BrokerID': self.brokerID,
            'InvestorID': self.userID
        }
        self.reqQryInvestorPosition(req, self.reqID)

    def onRspQryInvestorPosition(self, data, error, n, last):
        """持仓查询回报"""
        logging.info('onRspQryInvestorPosition time: %s', time.time())
        logging.info('onRspQryInvestorPosition data: %s', data)
        msg = {
            'msg_type': 'position',
            'data': data
        }
        self.queue.put(json.dumps(msg))

        # if not data['InstrumentID']:
        #     return
        #
        # # 获取持仓缓存对象
        # posName = '.'.join([data['InstrumentID'], data['PosiDirection']])
        # if posName in self.posDict:
        #     pos = self.posDict[posName]
        # else:
        #     pos = VtPositionData()
        #     self.posDict[posName] = pos
        #
        #     pos.gatewayName = self.gatewayName
        #     pos.symbol = data['InstrumentID']
        #     pos.vtSymbol = pos.symbol
        #     pos.direction = posiDirectionMapReverse.get(data['PosiDirection'], '')
        #     pos.vtPositionName = '.'.join([pos.vtSymbol, pos.direction])
        #
        # exchange = self.symbolExchangeDict.get(pos.symbol, EXCHANGE_UNKNOWN)
        #
        # # 针对上期所持仓的今昨分条返回（有昨仓、无今仓），读取昨仓数据
        # if exchange == EXCHANGE_SHFE:
        #     if data['YdPosition'] and not data['TodayPosition']:
        #         pos.ydPosition = data['Position']
        # # 否则基于总持仓和今持仓来计算昨仓数据
        # else:
        #     pos.ydPosition = data['Position'] - data['TodayPosition']
        #
        # # 计算成本
        # size = self.symbolSizeDict[pos.symbol]
        # cost = pos.price * pos.position * size

        # 汇总总仓
        # pos.position += data['Position']
        # pos.positionProfit += data['PositionProfit']
        #
        # # 计算持仓均价
        # if pos.position and size:
        #     pos.price = (cost + data['PositionCost']) / (pos.position * size)
        #
        # # 读取冻结
        # if pos.direction is DIRECTION_LONG:
        #     pos.frozen += data['LongFrozen']
        # else:
        #     pos.frozen += data['ShortFrozen']
        #
        # # 查询回报结束
        # if last:
        #     # 遍历推送
        #     for pos in self.posDict.values():
        #         self.gateway.onPosition(pos)
        #
        #     # 清空缓存
        #     self.posDict.clear()

    def sendOrder(self, order):
        """
        :param order:
        :return:
        """
        self.reqID += 1
        self.reqOrderInsert(order, self.reqID)
        order['RequestID'] = self.reqID
        order['FrontID'] = self.frontID
        order['SessionID'] = self.sessionID
        logging.info('sendOrder time: %s', time.time())
        logging.info('sendOrder data: %s', order)
        logging.info('=' * 30)

    def onRspOrderInsert(self, data, error, n, last):
        """发单错误（柜台）"""
        logging.info('onRspOrderInsert time: %s', time.time())
        logging.info('onRspOrderInsert data: %s', data)
        logging.info('onRspOrderInsert error: %s', error)
        data['ErrorID'] = error['ErrorID']
        data['ErrorMsg'] = error['ErrorMsg'].decode('gbk').encode('utf-8')
        data['callback'] = 'onRspOrderInsert'
        msg = {
            'msg_type': 'onRspOrderInsert',
            'data': data,
        }
        self.queue.put(json.dumps(msg))
        # 推送委托信息
        # order = VtOrderData()
        # order.gatewayName = self.gatewayName
        # order.symbol = data['InstrumentID']
        # order.exchange = exchangeMapReverse[data['ExchangeID']]
        # order.vtSymbol = order.symbol
        # order.orderID = data['OrderRef']
        # order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
        # order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        # order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        # order.status = STATUS_REJECTED
        # order.price = data['LimitPrice']
        # order.totalVolume = data['VolumeTotalOriginal']
        # self.gateway.onOrder(order)
        #
        # # 推送错误信息
        # err = VtErrorData()
        # err.gatewayName = self.gatewayName
        # err.errorID = error['ErrorID']
        # err.errorMsg = error['ErrorMsg'].decode('gbk')
        # self.gateway.onError(err)

    def onErrRtnOrderInsert(self, data, error):
        """发单错误回报（交易所）"""
        logging.info('onErrRtnOrderInsert time: %s', time.time())
        logging.info('onErrRtnOrderInsert data: %s', data)
        logging.info('onErrRtnOrderInsert error: %s', error)
        data['ErrorID'] = error['ErrorID']
        data['ErrorMsg'] = error['ErrorMsg'].decode('gbk').encode('utf-8')
        data['callback'] = 'onErrRtnOrderInsert'
        msg = {
            'msg_type': 'onErrRtnOrderInsert',
            'data': data
        }
        self.queue.put(json.dumps(msg))

        # 推送委托信息
        # order = VtOrderData()
        # order.gatewayName = self.gatewayName
        # order.symbol = data['InstrumentID']
        # order.exchange = exchangeMapReverse[data['ExchangeID']]
        # order.vtSymbol = order.symbol
        # order.orderID = data['OrderRef']
        # order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
        # order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        # order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        # order.status = STATUS_REJECTED
        # order.price = data['LimitPrice']
        # order.totalVolume = data['VolumeTotalOriginal']
        # self.gateway.onOrder(order)
        #
        # # 推送错误信息
        # err = VtErrorData()
        # err.gatewayName = self.gatewayName
        # err.errorID = error['ErrorID']
        # err.errorMsg = error['ErrorMsg'].decode('gbk')
        # self.gateway.onError(err)

    def onRtnOrder(self, data):
        """报单回报"""
        logging.info('onRtnOrder time: %s', time.time())
        logging.info('onRtnOrder data: %s', data)
        if str(data['SessionID']) == self.sessionID and str(data['FrontID']) == self.frontID:
            data['StatusMsg'] = data['StatusMsg'].decode('gbk').encode('utf-8')
            data['callback'] = 'onRtnOrder'
            self.exchange_id = str(data['ExchangeID'])
            self.order_sys_id = str(data['OrderSysID']).strip()
            msg = {
                'msg_type': 'onRtnOrder',
                'data': data,
            }
            self.queue.put(json.dumps(msg))

        # 更新最大报单编号
        # newref = data['OrderRef']
        # self.orderRef = max(self.orderRef, int(newref))
        #
        # # 创建报单数据对象
        # order = VtOrderData()
        # order.gatewayName = self.gatewayName
        #
        # # 保存代码和报单号
        # order.symbol = data['InstrumentID']
        # order.exchange = exchangeMapReverse[data['ExchangeID']]
        # order.vtSymbol = order.symbol  # '.'.join([order.symbol, order.exchange])
        #
        # order.orderID = data['OrderRef']
        # # CTP的报单号一致性维护需要基于frontID, sessionID, orderID三个字段
        # # 但在本接口设计中，已经考虑了CTP的OrderRef的自增性，避免重复
        # # 唯一可能出现OrderRef重复的情况是多处登录并在非常接近的时间内（几乎同时发单）
        # # 考虑到VtTrader的应用场景，认为以上情况不会构成问题
        # order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
        #
        # order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        # order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        # order.status = statusMapReverse.get(data['OrderStatus'], STATUS_UNKNOWN)
        #
        # # 价格、报单量等数值
        # order.price = data['LimitPrice']
        # order.totalVolume = data['VolumeTotalOriginal']
        # order.tradedVolume = data['VolumeTraded']
        # order.orderTime = data['InsertTime']
        # order.cancelTime = data['CancelTime']
        # order.frontID = data['FrontID']
        # order.sessionID = data['SessionID']
        #
        # # 推送
        # self.gateway.onOrder(order)

    def onRtnTrade(self, data):
        """成交回报"""
        logging.info('onRtnTrade time: %s', time.time())
        logging.info('onRtnTrade data: %s', data)
        data['callback'] = 'onRtnTrade'
        logging.info('self.exchange_id = %s', self.exchange_id)
        logging.info('self.order_sys_id = %s', self.order_sys_id)
        if data['ExchangeID'] == self.exchange_id and str(data['OrderSysID']).strip() == self.order_sys_id:
            msg = {
                'msg_type': 'onRtnTrade',
                'data': data
            }
            self.queue.put(json.dumps(msg))
            logging.info('put onRtnTrade data into queue!')

        # 创建报单数据对象
        # trade = VtTradeData()
        # trade.gatewayName = self.gatewayName
        #
        # # 保存代码和报单号
        # trade.symbol = data['InstrumentID']
        # trade.exchange = exchangeMapReverse[data['ExchangeID']]
        # trade.vtSymbol = trade.symbol  # '.'.join([trade.symbol, trade.exchange])
        #
        # trade.tradeID = data['TradeID']
        # trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])
        #
        # trade.orderID = data['OrderRef']
        # trade.vtOrderID = '.'.join([self.gatewayName, trade.orderID])
        #
        # # 方向
        # trade.direction = directionMapReverse.get(data['Direction'], '')
        #
        # # 开平
        # trade.offset = offsetMapReverse.get(data['OffsetFlag'], '')
        #
        # # 价格、报单量等数值
        # trade.price = data['Price']
        # trade.volume = data['Volume']
        # trade.tradeTime = data['TradeTime']
        #
        # # 推送
        # self.gateway.onTrade(trade)

    def cancelOrder(self, order):
        """撤单"""
        self.reqID += 1
        logging.info('cancelOrder data: %s', order)
        self.reqOrderAction(order, self.reqID)

        # req = dict()
        # req['InstrumentID'] = cancelOrderReq.symbol
        # req['ExchangeID'] = cancelOrderReq.exchange
        # req['OrderRef'] = cancelOrderReq.orderID
        # req['FrontID'] = cancelOrderReq.frontID
        # req['SessionID'] = cancelOrderReq.sessionID
        #
        # req['ActionFlag'] = defineDict['THOST_FTDC_AF_Delete']
        # req['BrokerID'] = self.brokerID
        # req['InvestorID'] = self.userID
        #
        # self.reqOrderAction(req, self.reqID)

    def onRspOrderAction(self, data, error, n, last):
        """撤单错误（柜台）"""
        logging.info('onRspOrderAction data: %s', data)
        logging.info('onRspOrderAction error: %s', error)
        data['ErrorID'] = error['ErrorID']
        data['ErrorMsg'] = error['ErrorMsg'].decode('gbk').encode('utf-8')
        data['callback'] = 'onRspOrderAction'
        msg = {
            'msg_type': 'onRspOrderAction',
            'data': data,
        }
        self.queue.put(json.dumps(msg))
        # err = VtErrorData()
        # err.gatewayName = self.gatewayName
        # err.errorID = error['ErrorID']
        # err.errorMsg = error['ErrorMsg'].decode('gbk')
        # self.gateway.onError(err)

    def onErrRtnOrderAction(self, data, error):
        """撤单错误回报（交易所）"""
        logging.info('onErrRtnOrderAction data: %s', data)
        logging.info('onErrRtnOrderAction error: %s', error)
        data['ErrorID'] = error['ErrorID']
        data['ErrorMsg'] = error['ErrorMsg'].decode('gbk').encode('utf-8')
        data['callback'] = 'onErrRtnOrderAction'
        msg = {
            'msg_type': 'onErrRtnOrderAction',
            'data': data,
        }
        self.queue.put(json.dumps(msg))
        # err = VtErrorData()
        # err.gatewayName = self.gatewayName
        # err.errorID = error['ErrorID']
        # err.errorMsg = error['ErrorMsg'].decode('gbk')
        # self.gateway.onError(err)

    def onRspError(self, error, n, last):
        """错误回报"""
        logging.info('onRspError time: %s', time.time())
        logging.info('onRspError data: %s', error)
        # self.order_queue.put(json.dumps(error))
        # err = VtErrorData()
        # err.gatewayName = self.gatewayName
        # err.errorID = error['ErrorID']
        # err.errorMsg = error['ErrorMsg'].decode('gbk')
        # self.gateway.onError(err)

    def onRspUserPasswordUpdate(self, data, error, n, last):
        """"""
        pass

    def onRspTradingAccountPasswordUpdate(self, data, error, n, last):
        """"""
        pass

    def onRspParkedOrderInsert(self, data, error, n, last):
        """"""
        pass

    def onRspParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    @staticmethod
    def get_temp_path():
        temp_path = os.path.join(os.getcwd(), 'trade_connect', str(random.randint(0, 99)))
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        path = os.path.join(temp_path, 'CTP_')

        return path

    def onRspQueryMaxOrderVolume(self, data, error, n, last):
        """"""
        pass

    def onRspRemoveParkedOrder(self, data, error, n, last):
        """"""
        pass

    def onRspRemoveParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspExecOrderInsert(self, data, error, n, last):
        """"""
        pass

    def onRspExecOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspForQuoteInsert(self, data, error, n, last):
        """"""
        pass

    def onRspQuoteInsert(self, data, error, n, last):
        """"""
        pass

    def onRspQuoteAction(self, data, error, n, last):
        """"""
        pass

    def onRspLockInsert(self, data, error, n, last):
        """"""
        pass

    def onRspCombActionInsert(self, data, error, n, last):
        """"""
        pass

    def onRspQryOrder(self, data, error, n, last):
        """"""
        pass

    def onRspQryTrade(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestor(self, data, error, n, last):
        """"""
        pass

    def onRspQryTradingCode(self, data, error, n, last):
        """"""
        pass

    def onRspQryInstrumentMarginRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryInstrumentCommissionRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchange(self, data, error, n, last):
        """"""
        pass

    def onRspQryProduct(self, data, error, n, last):
        """"""
        pass

    def onRspQryDepthMarketData(self, data, error, n, last):
        """"""
        pass

    def onRspQrySettlementInfo(self, data, error, n, last):
        """"""
        pass

    def onRspQryTransferBank(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorPositionDetail(self, data, error, n, last):
        """"""
        pass

    def onRspQryNotice(self, data, error, n, last):
        """"""
        pass

    def onRspQrySettlementInfoConfirm(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorPositionCombineDetail(self, data, error, n, last):
        """"""
        pass

    def onRspQryCFMMCTradingAccountKey(self, data, error, n, last):
        """"""
        pass

    def onRspQryEWarrantOffset(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorProductGroupMargin(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeMarginRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeMarginRateAdjust(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeRate(self, data, error, n, last):
        """"""
        pass

    def onRspQrySecAgentACIDMap(self, data, error, n, last):
        """"""
        pass

    def onRspQryProductExchRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryProductGroup(self, data, error, n, last):
        """"""
        pass

    def onRspQryOptionInstrTradeCost(self, data, error, n, last):
        """"""
        pass

    def onRspQryOptionInstrCommRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryExecOrder(self, data, error, n, last):
        """"""
        pass

    def onRspQryForQuote(self, data, error, n, last):
        """"""
        pass

    def onRspQryQuote(self, data, error, n, last):
        """"""
        pass

    def onRspQryLock(self, data, error, n, last):
        """"""
        pass

    def onRspQryLockPosition(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorLevel(self, data, error, n, last):
        """"""
        pass

    def onRspQryExecFreeze(self, data, error, n, last):
        """"""
        pass

    def onRspQryCombInstrumentGuard(self, data, error, n, last):
        """"""
        pass

    def onRspQryCombAction(self, data, error, n, last):
        """"""
        pass

    def onRspQryTransferSerial(self, data, error, n, last):
        """"""
        pass

    def onRspQryAccountregister(self, data, error, n, last):
        """"""
        pass

    def onRtnInstrumentStatus(self, data):
        """"""
        pass

    def onRtnTradingNotice(self, data):
        """"""
        pass

    def onRtnErrorConditionalOrder(self, data):
        """"""
        pass

    def onRtnExecOrder(self, data):
        """"""
        pass

    def onErrRtnExecOrderInsert(self, data, error):
        """"""
        pass

    def onErrRtnExecOrderAction(self, data, error):
        """"""
        pass

    def onErrRtnForQuoteInsert(self, data, error):
        """"""
        pass

    def onRtnQuote(self, data):
        """"""
        pass

    def onErrRtnQuoteInsert(self, data, error):
        """"""
        pass

    def onErrRtnQuoteAction(self, data, error):
        """"""
        pass

    def onRtnForQuoteRsp(self, data):
        """"""
        pass

    def onRtnCFMMCTradingAccountToken(self, data):
        """"""
        pass

    def onRtnLock(self, data):
        """"""
        pass

    def onErrRtnLockInsert(self, data, error):
        """"""
        pass

    def onRtnCombAction(self, data):
        """"""
        pass

    def onErrRtnCombActionInsert(self, data, error):
        """"""
        pass

    def onRspQryContractBank(self, data, error, n, last):
        """"""
        pass

    def onRspQryParkedOrder(self, data, error, n, last):
        """"""
        pass

    def onRspQryParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspQryTradingNotice(self, data, error, n, last):
        """"""
        pass

    def onRspQryBrokerTradingParams(self, data, error, n, last):
        """"""
        pass

    def onRspQryBrokerTradingAlgos(self, data, error, n, last):
        """"""
        pass

    def onRspQueryCFMMCTradingAccountToken(self, data, error, n, last):
        """"""
        pass

    def onRtnFromBankToFutureByBank(self, data):
        """"""
        pass

    def onRtnFromFutureToBankByBank(self, data):
        """"""
        pass

    def onRtnRepealFromBankToFutureByBank(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByBank(self, data):
        """"""
        pass

    def onRtnFromBankToFutureByFuture(self, data):
        """"""
        pass

    def onRtnFromFutureToBankByFuture(self, data):
        """"""
        pass

    def onRtnRepealFromBankToFutureByFutureManual(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByFutureManual(self, data):
        """"""
        pass

    def onRtnQueryBankBalanceByFuture(self, data):
        """"""
        pass

    def onErrRtnBankToFutureByFuture(self, data, error):
        """"""
        pass

    def onErrRtnFutureToBankByFuture(self, data, error):
        """"""
        pass

    def onErrRtnRepealBankToFutureByFutureManual(self, data, error):
        """"""
        pass

    def onErrRtnRepealFutureToBankByFutureManual(self, data, error):
        """"""
        pass

    def onErrRtnQueryBankBalanceByFuture(self, data, error):
        """"""
        pass

    def onRtnRepealFromBankToFutureByFuture(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByFuture(self, data):
        """"""
        pass

    def onRspFromBankToFutureByFuture(self, data, error, n, last):
        """"""
        pass

    def onRspFromFutureToBankByFuture(self, data, error, n, last):
        """"""
        pass

    def onRspQueryBankAccountMoneyByFuture(self, data, error, n, last):
        """"""
        pass

    def onRtnOpenAccountByBank(self, data):
        """"""
        pass

    def onRtnCancelAccountByBank(self, data):
        """"""
        pass

    def onRtnChangeAccountByBank(self, data):
        """"""
        pass
