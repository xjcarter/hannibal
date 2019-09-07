

from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedDaily
from Optimizer import Optimizer


if __name__ == '__main__':

    optimizer = Optimizer()
    optimizer.strategy_class = RetraceStrategy
   # optimizer.data_feed = DataFeedDaily('daily.SPY.csv')
    optimizer.data_feed = DataFeedDaily('SPY.csv')

    ## set population size
    optimizer.size = 40 
    optimizer.max_generations = 50
    optimizer.outfile = 'optimize_retrace3.xls'
    optimizer.reset_on_EOD = True

    ## parameter space to search over
    ## strategy_params for RetraceStrategy = dict(average,momentum,duration)
    ## momentum = entry momentum crossover
    ## average = moving average filter
    ## duration = trade holding period
     
    param_list = [dict(name='momentum',min_val=30,max_val=50,steps=16,converter=int),
                  dict(name='average',min_val=70,max_val=120,steps=32,converter=int),
                  dict(name='duration',min_val=10,max_val=20,steps=8,converter=int) ]

    for p in param_list:
        optimizer.add_parameter(p)

    optimizer.run()


































