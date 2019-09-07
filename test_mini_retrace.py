

from Simulator import Simulator
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList


if __name__ == '__main__':

	r = RetraceStrategy('retrace_mini_universe',strategy_params=dict(average=150,duration=20,momentum=65))
	d = DataFeedList(['mini_data.csv'],data_type='D')

	s = Simulator()
	s.add_strategy(r)
	s.run(d)

	s.write('retrace_mini_universe')
