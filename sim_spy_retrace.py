

from Simulator import Simulator
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList


if __name__ == '__main__':

	r = RetraceStrategy('retrace_mini',strategy_params=dict(average=150,duration=20,momentum=65))
	d = DataFeedList(['SPY.csv'],data_type='D')

	s = Simulator()
	s.add_strategy(r)
	s.run(d)

	s.write('retrace_spy_universe')
