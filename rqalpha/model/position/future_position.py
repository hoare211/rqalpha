# -*- coding: utf-8 -*-
#
# Copyright 2017 Ricequant, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import six

from .base_position import BasePosition
from ...execution_context import ExecutionContext
from ...environment import Environment
from ...const import ACCOUNT_TYPE, SIDE, POSITION_EFFECT


FuturePersistMap = {
    "_order_book_id": "_order_book_id",
    "_last_price": "_last_price",
    "_market_value": "_market_value",
    "_buy_order_quantity": "_buy_order_quantity",
    "_sell_order_quantity": "_sell_order_quantity",
    "_total_orders": "_total_orders",
    "_total_trades": "_total_trades",
    "_is_traded": "_is_traded",
    "_buy_open_order_quantity": "_buy_open_order_quantity",
    "_sell_open_order_quantity": "_sell_open_order_quantity",
    "_buy_close_order_quantity": "_buy_close_order_quantity",
    "_sell_close_order_quantity": "_sell_close_order_quantity",
    "_daily_realized_pnl": "_daily_realized_pnl",
    "_prev_settle_price": "_prev_settle_price",
    "_buy_old_holding_list": "_buy_old_holding_list",
    "_sell_old_holding_list": "_sell_old_holding_list",
    "_buy_today_holding_list": "_buy_today_holding_list",
    "_sell_today_holding_list": "_sell_today_holding_list",
    "_contract_multiplier": "_contract_multiplier",
    "_de_listed_date": "_de_listed_date",
    "_buy_transaction_cost": "_buy_transaction_cost",
    "_sell_transaction_cost": "_sell_transaction_cost",
    "_buy_daily_realized_pnl": "_buy_daily_realized_pnl",
    "_sell_daily_realized_pnl": "_sell_daily_realized_pnl",
    "_buy_avg_open_price": "_buy_avg_open_price",
    "_sell_avg_open_price": "_sell_avg_open_price",
}


class FuturePosition(BasePosition):

    # buy_open_order_quantity:    <float> 买开挂单量
    # sell_open_order_quantity:   <float> 卖开挂单量
    # buy_close_order_quantity:   <float> 买平挂单量
    # sell_close_order_quantity:  <float> 卖平挂单量

    # daily_realized_pnl:         <float> 当日平仓盈亏
    # buy_settle_holding:         <Tuple(price, amount)> 买结算后昨仓
    # sell_settle_holding:        <Tuple(price, amount)> 卖结算后昨仓
    # buy_today_holding_list:     <List<Tuple(price, amount)>> 买当日持仓队列
    # sell_today_holding_list:    <List<Tuple(price, amount)>> 卖当日持仓队列

    def __init__(self, order_book_id):
        super(FuturePosition, self).__init__(order_book_id)

        self._buy_open_order_quantity = 0
        self._sell_open_order_quantity = 0
        self._buy_close_order_quantity = 0  # sell_frozen_quantity
        self._sell_close_order_quantity = 0

        self._daily_realized_pnl = 0.
        self._prev_settle_price = 0.
        self._buy_old_holding_list = []         # [(price, amount)]
        self._sell_old_holding_list = []        # [(price, amount)]
        self._buy_today_holding_list = []       # [(price, amount)]
        self._sell_today_holding_list = []      # [(price, amount)]
        instrument = ExecutionContext.get_instrument(self.order_book_id)
        if instrument is None:
            self._contract_multiplier = None
            self._de_listed_date = None
        else:
            self._contract_multiplier = instrument.contract_multiplier
            self._de_listed_date = instrument.de_listed_date

        self._buy_transaction_cost = 0.
        self._sell_transaction_cost = 0.
        self._buy_daily_realized_pnl = 0.
        self._sell_daily_realized_pnl = 0.
        self._buy_avg_open_price = 0.
        self._sell_avg_open_price = 0.

    @classmethod
    def __from_dict__(cls, position_dict):
        position = cls(position_dict["_order_book_id"])
        for persist_key, origin_key in six.iteritems(FuturePersistMap):
            try:
                setattr(position, origin_key, position_dict[persist_key])
            except KeyError as e:
                if persist_key in ["_buy_avg_open_price", "_sell_avg_open_price"]:
                    # FIXME 对于已有 persist_key 做暂时error handling 处理。
                    setattr(position, origin_key, 0.)
                else:
                    raise e
        return position

    @classmethod
    def from_recovery(cls, order_book_id, position_dict, orders, trades):
        """
        position_dict = {
            'buy_quantity': None,
            'sell_quantity': None,
            'buy_today_quantity': None,
            'sell_today_quantity': None,
            'buy_transaction_cost': None,
            'sell_transaction_cost': None,
            'buy_avg_open_price': None,
            'sell_avg_open_price': None,
            'buy_daily_realized_pnl': None,
            'sell_daily_realized_pnl': None,
            'prev_settle_price': None,
        }
        """
        position = cls(order_book_id)

        for order in orders:
            if order.side == SIDE.BUY:
                if order.position_effect == POSITION_EFFECT.OPEN:
                    position._buy_open_order_quantity += order.unfilled_quantity
                else:
                    position._buy_close_order_quantity += order.unfilled_quantity
            else:
                if order.position_effect == POSITION_EFFECT.OPEN:
                    pass
                    position._sell_open_order_quantity += order.unfilled_quantity
                else:
                    position._sell_close_order_quantity += order.unfilled_quantity

        if 'prev_settle_price':
            position._prev_settle_price = position_dict['prev_settle_price']

        if 'buy_today_quantity' not in position_dict:
            position_dict['buy_today_quantity'] = 0

        if 'sell_today_quantity' not in position_dict:
            position_dict['sell_today_quantity'] = 0

        if 'buy_quantity' in position_dict:
            buy_old_quantity = position_dict['buy_quantity'] - position_dict['buy_today_quantity']
            position._buy_old_holding_list = [(position._prev_settle_price, buy_old_quantity)]

        if 'sell_quantity' in position_dict:
            sell_old_quantity = position_dict['sell_quantity'] - position_dict['sell_today_quantity']
            position._sell_old_holding_list = [(position._prev_settle_price, sell_old_quantity)]

        accum_buy_open_quantity = 0.
        accum_sell_open_quantity = 0.
        trades = sorted(trades, key=lambda t: t.datetime, reverse=True)
        for trade in trades:
            order = trade.order
            if order.side == SIDE.BUY:
                if order.position_effect == POSITION_EFFECT.OPEN:
                    accum_buy_open_quantity += trade.last_quantity
                    if accum_buy_open_quantity == position_dict['buy_today_quantity']:
                        break
                    if accum_buy_open_quantity > position_dict['buy_today_quantity']:
                        position._buy_today_holding_list.append((
                            trade.last_price,
                            position.buy_today_quantity - accum_buy_open_quantity + trade.last_quantity
                        ))
                        break
                    position._buy_today_holding_list.append((trade.last_price, trade.last_quantity))
            else:
                if order.position_effect == POSITION_EFFECT.OPEN:
                    accum_sell_open_quantity += trade.last_quantity
                    if accum_sell_open_quantity == position_dict['sell_today_quantity']:
                        break
                    if accum_sell_open_quantity > position_dict['sell_today_quantity']:
                        position._sell_today_holding_list.append((
                            trade.last_price,
                            position.sell_today_quantity - accum_sell_open_quantity + trade.last_quantity
                        ))
                        break
                    position._sell_today_holding_list.append((trade.last_price, trade.last_quantity))

        if 'buy_transaction_cost' in position_dict:
            position._buy_transaction_cost = position_dict['buy_transaction_cost']
        if 'sell_transaction_cost' in position_dict:
            position._sell_transaction_cost = position_dict['sell_transaction_cost']
        if 'buy_daily_realized_pnl' in position_dict:
            position._buy_daily_realized_pnl = position_dict['buy_daily_realized_pnl']
        if 'sell_daily_realized_pnl' in position_dict:
            position._sell_daily_realized_pnl = position_dict['sell_daily_realized_pnl']
        position._daily_realized_pnl = position._buy_daily_realized_pnl + position._sell_daily_realized_pnl

        if 'buy_avg_open_price' in position_dict:
            position._buy_avg_open_price = position_dict['buy_avg_open_price']
        if 'sell_avg_open_price' in position_dict:
            position._sell_avg_open_price = position_dict['sell_avg_open_price']
        return position

    def __to_dict__(self):
        p_dict = {}
        for persist_key, origin_key in six.iteritems(FuturePersistMap):
            p_dict[persist_key] = getattr(self, origin_key)
        return p_dict

    @property
    def buy_open_order_quantity(self):
        """
        【int】买开挂单量
        """
        return self._buy_open_order_quantity

    @property
    def sell_open_order_quantity(self):
        """
        【int】卖开挂单量
        """
        return self._sell_open_order_quantity

    @property
    def buy_close_order_quantity(self):
        """
        【int】买平挂单量
        """
        return self._buy_close_order_quantity

    @property
    def sell_close_order_quantity(self):
        """
        【int】卖平挂单量
        """
        return self._sell_close_order_quantity

    @property
    def daily_realized_pnl(self):
        """
        【float】当日平仓盈亏
        """
        return self._daily_realized_pnl

    @property
    def daily_pnl(self):
        """
        【float】当日盈亏，当日浮动盈亏+当日平仓盈亏
        """
        return self.daily_realized_pnl + self.daily_holding_pnl

    @property
    def daily_holding_pnl(self):
        """
        【float】当日持仓盈亏
        """
        # daily_holding_pnl: < float > 当日持仓盈亏
        return self._market_value + self._sell_holding_cost - self._buy_holding_cost

    @property
    def _buy_daily_holding_pnl(self):
        return (self._last_price - self.buy_avg_holding_price) * self.buy_quantity * self._contract_multiplier

    @property
    def _sell_daily_holding_pnl(self):
        return (self.sell_avg_holding_price - self._last_price) * self.sell_quantity * self._contract_multiplier

    @property
    def buy_daily_pnl(self):
        """
        【float】多头仓位当日盈亏
        """
        return self._buy_daily_holding_pnl + self._buy_daily_realized_pnl

    @property
    def sell_daily_pnl(self):
        """
        【float】空头仓位当日盈亏
        """
        return self._sell_daily_holding_pnl + self._sell_daily_realized_pnl

    @property
    def margin(self):
        """
        【float】仓位总保证金
        """
        # 总保证金
        # TODO 这里之后需要进行修改,需要考虑单向大边的情况
        return self.buy_margin + self.sell_margin

    @property
    def buy_margin(self):
        """
        【float】多头持仓占用保证金
        """
        # buy_margin: < float > 买保证金
        margin_decider = Environment.get_instance().accounts[ACCOUNT_TYPE.FUTURE].margin_decider
        return margin_decider.cal_margin(self.order_book_id, SIDE.BUY, self._buy_holding_cost)

    @property
    def sell_margin(self):
        """
        【float】空头持仓占用保证金
        """
        # sell_margin: < float > 卖保证金
        margin_decider = Environment.get_instance().accounts[ACCOUNT_TYPE.FUTURE].margin_decider
        return margin_decider.cal_margin(self.order_book_id, SIDE.SELL, self._sell_holding_cost)

    @property
    def _buy_old_holding_quantity(self):
        return sum(amount for price, amount in self._buy_old_holding_list)

    @property
    def _sell_old_holding_quantity(self):
        return sum(amount for price, amount in self._sell_old_holding_list)

    @property
    def _buy_today_holding_quantity(self):
        return sum(amount for price, amount in self._buy_today_holding_list)

    @property
    def _sell_today_holding_quantity(self):
        return sum(amount for price, amount in self._sell_today_holding_list)

    @property
    def buy_quantity(self):
        """
        【int】多头持仓
        """
        # 买方向总持仓
        return self._buy_old_holding_quantity + self._buy_today_holding_quantity

    @property
    def sell_quantity(self):
        """
        【int】空头持仓
        """
        # 卖方向总持仓
        return self._sell_old_holding_quantity + self._sell_today_holding_quantity

    @property
    def buy_avg_holding_price(self):
        """
        【float】多头持仓均价
        """
        return 0 if self.buy_quantity == 0 else self._buy_holding_cost / self.buy_quantity / self._contract_multiplier

    @property
    def sell_avg_holding_price(self):
        """
        【float】空头持仓均价
        """
        return 0 if self.sell_quantity == 0 else self._sell_holding_cost / self.sell_quantity / self._contract_multiplier

    @property
    def _buy_closable_quantity(self):
        # 买方向可平仓量
        return self.buy_quantity - self._sell_close_order_quantity

    @property
    def _sell_closable_quantity(self):
        # 卖方向可平仓量
        return self.sell_quantity - self._buy_close_order_quantity

    @property
    def closable_buy_quantity(self):
        """
        【float】可平多头持仓
        """
        return self._buy_closable_quantity

    @property
    def closable_sell_quantity(self):
        """
        【int】可平空头持仓
        """
        return self._sell_closable_quantity

    @property
    def _buy_old_holding_cost(self):
        return self._buy_old_holding_quantity * self._prev_settle_price * self._contract_multiplier

    @property
    def _sell_old_holding_cost(self):
        return self._sell_old_holding_quantity * self._prev_settle_price * self._contract_multiplier

    @property
    def _buy_today_holding_cost(self):
        return sum(p * a * self._contract_multiplier for p, a in self._buy_today_holding_list)

    @property
    def _sell_today_holding_cost(self):
        return sum(p * a * self._contract_multiplier for p, a in self._sell_today_holding_list)

    @property
    def _buy_holding_cost(self):
        return self._buy_old_holding_cost + self._buy_today_holding_cost

    @property
    def _sell_holding_cost(self):
        return self._sell_old_holding_cost + self._sell_today_holding_cost

    @property
    def _quantity(self):
        return self.buy_quantity + self.sell_quantity

    @property
    def _position_value(self):
        # 总保证金 + 当日持仓盈亏 + 当日平仓盈亏
        return self.margin + self.daily_holding_pnl + self.daily_realized_pnl

    @property
    def buy_today_quantity(self):
        """
        【int】多头今仓
        """
        # Buy今仓
        return sum(amount for (price, amount) in self._buy_today_holding_list)

    @property
    def sell_today_quantity(self):
        """
        【int】空头今仓
        """
        # Sell今仓
        return sum(amount for (price, amount) in self._sell_today_holding_list)

    @property
    def _closable_buy_today_quantity(self):
        return self.buy_today_quantity - self._sell_close_order_quantity

    @property
    def _closable_sell_today_quantity(self):
        return self.sell_today_quantity - self._buy_close_order_quantity

    @property
    def buy_pnl(self):
        """
        【float】多头仓位累计盈亏
        """
        return (self._last_price - self._buy_avg_open_price) * self.buy_quantity * self._contract_multiplier

    @property
    def sell_pnl(self):
        """
        【float】空头仓位累计盈亏
        """
        return (self._last_price - self._sell_avg_open_price) * self.sell_quantity * self._contract_multiplier

    @property
    def buy_daily_pnl(self):
        """
        【float】多头仓位当日盈亏
        """
        return self._buy_daily_holding_pnl + self._buy_daily_realized_pnl

    @property
    def sell_daily_pnl(self):
        """
        【float】空头仓位当日盈亏
        """
        return self._sell_daily_holding_pnl + self._sell_daily_realized_pnl

    @property
    def _buy_holding_list(self):
        return self._buy_old_holding_list + self._buy_today_holding_list

    @property
    def _sell_holding_list(self):
        return self._sell_old_holding_list + self._sell_today_holding_list

    @property
    def buy_avg_open_price(self):
        """
        【float】多头持仓均价
        """
        return self._buy_avg_open_price

    @property
    def sell_avg_open_price(self):
        """
        【float】空头开仓均价
        """
        return self._sell_avg_open_price

    @property
    def buy_transaction_cost(self):
        """
        【float】多头费用
        """
        return self._buy_transaction_cost

    @property
    def sell_transaction_cost(self):
        """
        【float】空头费用
        """
        return self._sell_transaction_cost

    @property
    def transaction_cost(self):
        """
        【float】仓位交易费用
        """
        return self.buy_transaction_cost + self.sell_transaction_cost

    def _cal_close_today_amount(self, trade_amount, trade_side):
        if trade_side == SIDE.SELL:
            close_today_amount = trade_amount - self._buy_old_holding_quantity
        else:
            close_today_amount = trade_amount - self._sell_old_holding_quantity
        return max(close_today_amount, 0)
