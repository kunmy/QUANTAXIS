# coding :utf-8
#
# The MIT License (MIT)
#
# Copyright (c) 2016-2017 yutiansut/QUANTAXIS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import datetime
import threading
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Event, Thread, Timer

from QUANTAXIS.QAARP.QAAccount import QA_Account
from QUANTAXIS.QAEngine.QAEvent import QA_Event, QA_Job
from QUANTAXIS.QAEngine.QATask import QA_Task
from QUANTAXIS.QAFetch.QAQuery import (QA_fetch_future_day,
                                       QA_fetch_future_min,
                                       QA_fetch_future_tick,
                                       QA_fetch_index_day, QA_fetch_index_min,
                                       QA_fetch_stock_day, QA_fetch_stock_min)
from QUANTAXIS.QAFetch.QATdx import (QA_fetch_get_future_day,
                                     QA_fetch_get_future_min,
                                     QA_fetch_get_future_transaction,
                                     QA_fetch_get_future_transaction_realtime,
                                     QA_fetch_get_index_day,
                                     QA_fetch_get_index_min,
                                     QA_fetch_get_stock_day,
                                     QA_fetch_get_stock_min)
from QUANTAXIS.QAMarket.QABacktestBroker import QA_BacktestBroker
from QUANTAXIS.QAMarket.QABroker import QA_Broker
from QUANTAXIS.QAMarket.QADealer import QA_Dealer
from QUANTAXIS.QAMarket.QAOrderHandler import QA_OrderHandler
from QUANTAXIS.QAMarket.QARandomBroker import QA_RandomBroker
from QUANTAXIS.QAMarket.QARealBroker import QA_RealBroker
from QUANTAXIS.QAMarket.QASimulatedBroker import QA_SimulatedBroker
from QUANTAXIS.QAMarket.QATrade import QA_Trade
from QUANTAXIS.QAUtil.QALogs import QA_util_log_info
from QUANTAXIS.QAUtil.QAParameter import (ACCOUNT_EVENT, AMOUNT_MODEL,
                                          BROKER_EVENT, BROKER_TYPE,
                                          MARKET_EVENT, ORDER_DIRECTION,
                                          ORDER_EVENT, ORDER_MODEL,
                                          ORDER_STATUS, MARKETDATA_TYPE)


class QA_Market(QA_Trade):
    """
    QUANTAXIS MARKET 部分

    交易前置/可连接到多个broker中

    暂时还是采用多线程engine模式

    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.session = {}
        self.order_handler = QA_OrderHandler()
        self._broker = {BROKER_TYPE.BACKETEST: QA_BacktestBroker, BROKER_TYPE.RANODM: QA_RandomBroker,
                        BROKER_TYPE.REAL: QA_RealBroker, BROKER_TYPE.SIMULATION: QA_SimulatedBroker}
        
        self.broker = {}
        self.running_time = None

    def __repr__(self):
        return '< QA_MARKET with {} Broker >'.format(list(self.broker.keys()))

    def start(self):
        self.trade_engine.start()
        # self.trade_engine.create_kernal('MARKET')
        # self.trade_engine.start_kernal('MARKET')

    def connect(self, broker):
        if broker in self._broker.keys():

            self.broker[broker] = self._broker[broker]()# 在这里实例化
            self.trade_engine.create_kernal('{}'.format(broker))
            self.trade_engine.start_kernal('{}'.format(broker))
            # 开启trade事件子线程
            return True
        else:
            return False

    def login(self, account_cookie):

        if account_cookie not in self.session.keys():
            self.session[account_cookie] = QA_Account(
                account_cookie=account_cookie)
        else:
            return False

    def logout(self, account_cookie):
        if account_cookie not in self.session.keys():
            return False
        else:
            self.session.pop(account_cookie)

    def get_trading_day(self):
        return self.running_time

    def get_account_id(self):
        return [item.account_cookie for item in self.session.values()]

    def insert_order(self, account_id, amount, amount_model, time, code, order_model, towards):

        order = self.session[account_id].send_order(
            amount=amount, amount_model=amount_model, time=time, code=code, order_model=order_model, towards=towards)
        #current_price = self.query_data(order.code, order.time)
        self.event_queue.put(QA_Task(job=self.order_handler, event=QA_Event(
            event_type=ORDER_EVENT.CREATE, message=order, callback=self.on_insert_order)))

    def on_insert_order(self, order):
        if order.status is ORDER_STATUS.QUEUED:
            if order.towards in [ORDER_DIRECTION.BUY]:
                #    self._broker[on_]
                pass

    def _renew_account(self):
        pass

    def query_order(self, order_id):
        return self.order_handler.order_queue.query_order(order_id)

    def query_asset(self, account_cookie):
        return self.session[account_cookie].cash

    def query_position(self, broker_name, account_cookie):
        self.event_queue.put(
            QA_Task(
                job=self.broker[broker_name],
                engine=broker_name,
                event=QA_Event(
                    event_type=MARKET_EVENT.QUERY_ACCOUNT,
                    message={
                        'account': account_cookie
                    },
                    callback=self.on_query_position
                )
            ))

    def on_query_position(self, data):
        pass

    def query_data(self, broker_name, data_type, market_type, code, start, end=None):
        self.event_queue.put(
            QA_Task(
                job=self.broker[broker_name],
                engine=broker_name,
                event=QA_Event(
                    event_type=MARKET_EVENT.QUERY_DATA,
                    message={
                        'data_type':  data_type,
                        'market_type': market_type,
                        'code': code,
                        'start': start,
                        'end': end
                    },
                    callback=self.on_query_data
                )
            ))

    def on_query_data(self, data):
        print('ON QUERY')
        print(data)

    def on_trade_event(self, data):
        print('ON_TRADE')
        print(data)

    def _trade(self):
        "内部函数"
        self.event_queue.put(QA_Task(job=self.order_handler, event=QA_Event(
            event_type=BROKER_EVENT.TRADE, message={'broker': self.broker}, callback=self.on_trade_event)))

    def _settle(self):
        # 向事件线程发送BROKER的SETTLE事件
        self.event_queue.put(QA_Task(job=self.order_handler, event=QA_Event(
            event_type=BROKER_EVENT.SETTLE, message={'broker': self.broker})))
        # 向事件线程发送ACCOUNT的SETTLE事件
        for item in self.session.values():
            self.event_queue.put(
                QA_Task(job=item, event=QA_Event(event_type=ACCOUNT_EVENT.SETTLE)))

    def _close(self):
        pass


if __name__ == '__main__':

    import QUANTAXIS as QA

    user = QA.QA_Portfolio()
    # 创建两个account

    a_1 = user.new_account()
    a_2 = user.new_account()
    market = QA_Market()

    market.connect(QA.RUNNING_ENVIRONMENT.BACKETEST)
    print(market)
    market.login(a_1)
    market.login(a_2)
    print(market.get_account_id())
    market.insert_order(account_id=a_1, amount=10000, amount_model=QA.AMOUNT_MODEL.BY_PRICE,
                        time='2017-12-14', code='000001', order_model=QA.ORDER_MODEL.CLOSE, towards=QA.ORDER_DIRECTION.BUY)