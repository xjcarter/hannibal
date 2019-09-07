
from Simulator import Simulator 
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList
from MStrategy2 import MStrategy2

s = Simulator()
'''
s.add_strategy(RetraceStrategy('R2',strategy_params = dict(average=141,momentum=21,duration=15)))
#data_feed = DataFeedList(['daily.SPY.csv','daily.SPY.csv'],data_type='D')
data_feed = DataFeedList(['daily.SPY.csv','daily.SPY.csv'],data_type='D')
s.run(data_feed)
s.write('R2')

## testing DataFeedBar serial files
strat = MStrategy2('M2',strategy_params = dict(length=20,duration=15))
#strat.capture_data = True
s.add_strategy(strat)
s.reset_on_EOD = False
data_feed = DataFeedList(['20081210.SPY.1min.csv','20081211.SPY.1min.csv','20081212.SPY.1min.csv'],data_type='B') 
s.run(data_feed)
#strat.dump_data().to_csv('M2_data_dump.csv')
s.write('M2')
'''

## testing DataFeedIntraday serial files
strat = MStrategy2('M2',strategy_params = dict(length=30,duration=50))
#strat.capture_data = True
s.add_strategy(strat)
s.reset_on_EOD = False
#data_feed = DataFeedList(['20081210.SPY.30s.csv','20081211.SPY.30s.csv'],data_type='I') 
#data_feed = DataFeedList(['combo.SPY.30s.csv'],data_type='I') 
data_feed = DataFeedList(['20081210.SPY.30s.csv','20081211.SPY.30s.csv','20081212.SPY.30s.csv'],data_type='I') 

s.run(data_feed)
#strat.dump_data().to_csv('M2_data_dump.csv')
s.write('MI2')
