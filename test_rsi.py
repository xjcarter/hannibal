

from RSIStrategy import RSIStrategy 
from DataFeed import DataFeedList
from Optimizer import Optimizer
from datetime import datetime


if __name__ == '__main__':

    optimizer = Optimizer()
    optimizer.strategy_class = RSIStrategy
    #optimizer.data_feed = DataFeedList(['20081210.SPY.1m.csv','20081211.SPY.1min.csv','20081212.SPY.1min.csv'],data_type='B') 
    #optimizer.data_feed = DataFeedList(['20081210.SPY.30s.csv','20081211.SPY.30s.csv','20081212.SPY.30s.csv'],data_type='I') 
    optimizer.data_feed = DataFeedList(['SPY.csv'],data_type='D') 

    ## set population size
    optimizer.size = 40 
    optimizer.max_generations = 50
    optimizer.outfile = '%s_%s.xls' % (__file__[:-3],datetime.now().strftime("%Y%m%d_%H%M"))
    optimizer.tolerance = 0.01
    #optimizer.reset_on_EOD = False 

    ## parameter space to search over
    ## rsi = rsi length
    ## top/btm = rsi buy sell thresholds
    ## average(optional) trend filter
    ## duration = trade duration
     
    optimizer.add_parameter(dict(name='rsi',min_val=10,max_val=40,steps=16,converter=int))
    optimizer.add_parameter(dict(name='top',min_val=60,max_val=80,steps=4,converter=int))
    optimizer.add_parameter(dict(name='btm',min_val=20,max_val=40,steps=4,converter=int))
    #optimizer.add_parameter(dict(name='average',min_val=20,max_val=100,steps=64,converter=int))
    optimizer.add_parameter(dict(name='duration',min_val=5,max_val=20,steps=8,converter=int))

    optimizer.run()


































