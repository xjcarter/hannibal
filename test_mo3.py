

from MStrategy3 import MStrategy3
from DataFeed import DataFeedList
from Optimizer import Optimizer


if __name__ == '__main__':

    optimizer = Optimizer()
    optimizer.strategy_class = MStrategy3
    #optimizer.data_feed = DataFeedList(['20081210.SPY.1m.csv','20081211.SPY.1min.csv','20081212.SPY.1min.csv'],data_type='B') 
    #optimizer.data_feed = DataFeedList(['20081210.SPY.30s.csv','20081211.SPY.30s.csv','20081212.SPY.30s.csv'],data_type='I') 
    optimizer.data_feed = DataFeedList(['SPY.csv'],data_type='D') 

    ## set population size
    optimizer.size = 40 
    optimizer.max_generations = 50
    optimizer.outfile = 'optimize_spy.xls'
    optimizer.tolerance = 0.01
    #optimizer.reset_on_EOD = False 

    ## parameter space to search over
    ## strategy_params for RetraceStrategy = dict(average,momentum,duration)
    ## momentum = entry momentum crossover
     
    optimizer.add_parameter(dict(name='avp',min_val=3,max_val=12,steps=8,converter=int))
    optimizer.add_parameter(dict(name='momentum',min_val=10,max_val=100,steps=64,converter=int))
    optimizer.add_parameter(dict(name='duration',min_val=5,max_val=20,steps=8,converter=int))

    optimizer.run()


































