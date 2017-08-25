#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-08-21 17:15:53
# @Author  : Li Hao (howardlee_h@outlook.com)
# @Link    : https://github.com/SAmmer0
# @Version : $Id$

# 标准库
from collections import OrderedDict
import pdb

# 第三方库
import pandas as pd
from tqdm import tqdm

# 本地库
from .utils import Stock, Portfolio
from ..utils import HDFDataProvider, NoneDataProvider
from dateshandle import get_tds

# ------------------------------------------------------------------------------


class BacktestConfig(object):
    '''
    回测配置设置类
    '''

    def __init__(self, start_date, end_date, quote_provider, weight_calculator, 
                 tradedata_provider, reb_calculator, group_num=10, commission_rate=0.,
                 init_cap=1e10, show_progress=True):
        '''
        Parameter
        ---------
        start_date: str, datetime or other compatible type
            回测开始时间
        end_date: str, datetime or other compatible type
            回测结束时间
        quote_provider: DataProvider
            计算净值用的数据提供器
        weight_calculator: WeightCalc
            权重计算器
        tradedata_provider: DataProvider
            能否交易的数据的提供器
        reb_calculator: RebCalc
            再平衡日计算器
        group_num: int
            因子测试分的组数
        commission_rate: float
            交易成本
        init_cap: float or int
            初始资本
        show_progress: bool, default True
            是否显示回测进度，默认显示
        '''
        self.start_date = start_date
        self.end_date = end_date
        self.quote_provider = quote_provider
        self.weight_calculator = weight_calculator
        self.tradedata_provider = tradedata_provider
        self.reb_calculator = reb_calculator
        self.group_num = group_num
        self.commission_rate = commission_rate
        self.init_cap = init_cap
        self.show_progress = show_progress


class Backtest(object):
    '''
    回测类
    '''

    def __init__(self, config, stock_filter, *args, **kwargs):
        '''
        Parameter
        ---------
        config: BacktestConfig
            回测相关配置
        stock_filter: function
            用于计算股票分组的函数，形式为function(date, *args, **kwargs)，返回值要求为
            {order: [secu_codes]}，其中order为对应股票组合的顺序，要求为range(0, config.group_num)
        args: tuple like arguments
            stock_filter需要使用的位置参数
        kwargs: dict like arguments
            stock_filter需要使用的键值参数
        '''
        self._config = config
        self._tds = get_tds(config.start_date, config.end_date)
        self.holding_result = OrderedDict()
        self.navs = OrderedDict()
        self._stock_filter = stock_filter
        self._args = args
        self._kwargs = kwargs
        self._ports = {i: Portfolio(self._config.init_cap) for i in range(self._config.group_num)}
        self._navs_pd = None
        self._offset = 10    # 避免满仓是因为小数点的问题导致资金溢出
    
    def build_portfolio(self, port_id, secu_list, date):
        '''
        建仓函数
        
        Parameter
        ---------
        port_id: str
            组合的编号
        secu_list: list of string
            需要加入组合的证券
        date: datetime or other compatible types
            加入组合的时间
        '''
        # 只买入今日能够交易的股票
        tradeable_stocks = self._config.tradedata_provider.get_csdata(date)
        tradeable_stocks = tradeable_stocks.loc[tradeable_stocks == 1].index.tolist()
        secu_list = list(set(secu_list).intersection(tradeable_stocks))
        #if len(secu_list) == 0:
            #pdb.set_trace()
        weights = self._config.weight_calculator(secu_list, date=date)  # 计算权重
        port = self._ports[port_id]
        port_mkv = port.sell_all(date) - self._offset    # 卖出全部金融工具
        weights = {code: Stock(code, quote_provider=self._config.quote_provider).\
                   construct_from_value(weights[code] * port_mkv, date)
                   for code in weights}
        # pdb.set_trace()
        port.buy_seculist(weights.values(), date)
        
    def run_bt(self):
        '''
        开启回测
        '''
        chg_pos_tag = False     # 用于标记是否到了换仓日
        chg_pos = None      # 用于记录下次换仓时持仓，类型为dict
        if self._config.show_progress:    # 需要显示进度
            tds_iter = zip(self._tds, tqdm(self._tds))
        else:
            tds_iter = enumerate(self._tds)
        for _idx, td in tds_iter:
            if chg_pos_tag:     # 表明当前需要换仓
                for port_id in self._ports:
                    self.build_portfolio(port_id, chg_pos[port_id], td)
                chg_pos_tag = False
                    
            if self._config.reb_calculator(td):     # 当前为计算日
                chg_pos = self._stock_filter(td, *self._args, **self._kwargs)
                chg_pos_tag = True
                self.holding_result[td] = chg_pos
            
            # 记录净值信息
            nav = {port_id: self._ports[port_id].refresh_value(td)
                   for port_id in self._ports}
            self.navs[td] = nav
    
    @property
    def navpd(self):
        '''
        pd.DataFrame格式的净值数据
        '''
        if self._navs_pd is not None:
            return self._navs_pd
        else:
            self._navs_pd = pd.DataFrame(self.navs).T
            return self._navs_pd
        