
from Treadmill import Treadmill
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList

'''
testing the EOD flag
making sure that treadmill output is consistent across multiple datafeed
versus if the datafeed where combined into single data file
'''

t = Treadmill()
t.strategy_class = RetraceStrategy
t.strategy_params = dict(average=141,momentum=21,duration=15)
#t.data_feed = DataFeedList(['daily.SPY.csv','daily.SPY.csv'],data_type='D')
t.data_feed = DataFeedList(['top.SPY.csv','bottom.SPY.csv'],data_type='D')
t.reset_on_EOD = False
t.run(20)