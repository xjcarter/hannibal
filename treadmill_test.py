
from Treadmill import Treadmill
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedDaily

t = Treadmill()
t.strategy_class = RetraceStrategy
t.strategy_params = dict(average=141,momentum=21,duration=15)
t.data_feed = DataFeedDaily('daily.SPY.csv')
t.run()