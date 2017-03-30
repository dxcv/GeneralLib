# -*- coding: utf-8 -*-
"""
Created on Tue Sep  6 17:03:08 2016

@author: hao
修改日志：
修改日期：2016年10月20日
修改内容：
    1. 添加函数extendNetValue，用于将净值扩展到期间的交易日，即对应策略期间每一个
       交易日，都有一个净值（目前考虑删除 2016年11月4日）
    2. 添加计算sharp比率的函数

修改日期：2016年12月1日
修改内容：
    在ret_stats函数中加入代码，使函数能够返回数据个数

修改日期：2016年12月13日
修改内容：
    在ret_stats函数中加入计算盈亏比的代码

__version__ = 1.1
修改日期：2017年3月29日
修改内容：
    1. 重构了最大回撤函数
    2. 重构了信息比率和夏普比率计算函数
"""
__version__ = 1.1
import pandas as pd
import numpy as np
import matplotlib.pylab as plt
import datatoolkits


def max_drawn_down(netValues, columnName=None):
    '''
    计算净值序列的最大回撤：maxDrawndDown = max(1-D_i/D_j) i > j
    @param:
        netValues 净值序列，可以是pd.DataFrame,pd.Series和np.array,list类型，如果时pd.DataFrame的类型，
            则默认净值所在的列列名为netValue，如果为其他列名，则需要自行通过columnName参数提供
    @return:
        (maxDrawnDown, startTime(or index), endTime(or index))
    '''
    if isinstance(netValues, list):
        nav = pd.Series(netValues)
    elif isinstance(netValues, pd.DataFrame):
        if columnName is None:
            nav = netValues['netValue']
        else:
            nav = netValues[columnName]
    else:
        nav = netValues
    cumMax = nav.cummax()
    dd = 1 - nav / cumMax
    mdd = dd.max()
    mddEndTime = dd.idxmax()
    mddStartTime = nav[nav == cumMax[mddEndTime]].index[0]
    return mdd, mddStartTime, mddEndTime


def ret_stats(retValues, columnName=None, displayHist=False):
    '''
    计算策略交易收益的统计数据，包含胜率、均值、中位数、最大值、最小值、峰度、偏度
    @param:
        retValues 收益率序列数据，要求为序列或者pd.DataFrame或者pd.Series类型
        columnName 若提供的数据类型为pd.DataFrame，默认为None表明retValues中
                   有retValues这列数据，否则则需要通过columnName来传入
        displayHist 若为True，则依照收益率序列画出直方图
    @return:
        [winProb, retMean, retMed, retMax, retMin, retKurtosis, retSkew]
    '''
    if not (isinstance(retValues, pd.DataFrame) or isinstance(retValues, pd.Series)):
        retValues = pd.Series(retValues)
    if isinstance(retValues, pd.DataFrame):
        if 'retValues' in retValues.columns:
            retValues = pd.Series(retValues['retValues'].values)
        else:
            if columnName is None:
                raise KeyError('optional parameter \'columnName\' should be provided by user')
            else:
                retValues = pd.Series(retValues[columnName].values)
    winProb = np.sum(retValues > 0) / len(retValues)
    count = len(retValues)
    if displayHist:
        plt.hist(retValues, bins=int(len(retValues / 30)))
    plRatio = (retValues[retValues > 0].sum() / abs(retValues[retValues <= 0].sum())
               if np.sum(retValues < 0) > 0 else float('inf'))
    return pd.Series({'winProb': winProb, 'PLRatio': plRatio, 'mean': retValues.mean(),
                      'median': retValues.median(), 'max': retValues.max(),
                      'min': retValues.min(), 'kurtosis': retValues.kurtosis(),
                      'skew': retValues.skew(), 'count': count})


def info_ratio(retValues, retFreq, benchMark=.0, columnName=None):
    '''
    计算策略的信息比率：
        info_ratio = annualized_ret(ret - benchMark)/annualized_std(ret-benchMark)
    @param:
        retValues 收益率序列数据，要求为序列或者pd.DataFrame或者pd.Series类型
        retFreq: 收益率数据的转化为年化的频率，例如，月度数据对应12，年度数据对应250
        benckMark: 基准收益率，默认为0，可以为DataFrame、Series、list和数值的形式，要求如果为DataFrame
            或者Series形式时，其index应该与收益率序列相同
        columnName 若提供的数据类型为pd.DataFrame，默认为None表明retValues中
                   有retValues这列数据，否则则需要通过columnName来传入
    @return:
        infoRatio 即根据上述公式计算出的信息比率
    '''
    if not isinstance(retValues, (pd.DataFrame, pd.Series)):
        retValues = pd.Series(retValues)
    if isinstance(retValues, pd.DataFrame):
        if 'retValues' in retValues.columns:
            retValues = retValues['retValues']
        else:
            if columnName is None:
                raise KeyError('optional parameter \'columnName\' should be provided by user')
            else:
                retValues = retValues[columnName]
    if not isinstance(benchMark, (float, int)):
        assert hasattr(benchMark, '__len__'), ValueError(
            'given benchMark should be series object, eg: list, pd.DataFrame, etc...')
        assert len(benchMark) == len(retValues), ValueError(
            'given benchMark should have the same length as retValues')
        if isinstance(benchMark, list):
            benchMark = pd.Series(benchMark, index=retValues.index)
    else:   # 现将基准转化为年化
        benchMark = pd.Series([datatoolkits.retfreq_trans(benchMark, 1 / retFreq)] * len(retValues),
                              index=retValues.index)
    excessRet = retValues - benchMark
    annualized_ret = datatoolkits.retfreq_trans(excessRet.mean(), retFreq)
    annualized_std = datatoolkits.annualize_std(excessRet.std(), excessRet.mean(), retFreq)
    return annualized_ret / annualized_std


def sharp_ratio(retValues, retFreq, riskFreeRate=.0, columnName=None):
    '''
    计算策略的夏普比率：
        sharp_ratio = annualiezd_ret(ret - riskFreeRate)/annualized_std(ret)
    注：要求ret与riskFreeRate的频率是相同的，比如都为年化的；由于夏普比率是信息比率的一种特殊情况，
        因此该函数通过调用信息比率函数计算
    @param:
        retValues 收益率序列数据，要求为序列或者pd.DataFrame或者pd.Series类型
        retFreq: 收益率数据的转化为年化的频率，例如，月度数据对应12，年度数据对应250
        riskFreeRate: 无风险利率，默认为.0
        columnName: 若提供的数据类型为pd.DataFrame，默认为None表明retValues中有retValues这列数据，
            否则需要通过columnName来传入
    @return:
        sharpRatio 即根据上述公式计算的夏普比率
    '''
    return info_ratio(retValues, retFreq, riskFreeRate, columnName)