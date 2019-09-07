

from Simulator import Simulator
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList


if __name__ == '__main__':

	r = RetraceStrategy('ret50',strategy_params=dict(average=100,duration=10,momentum=20))
	d = DataFeedList(['mini_data.csv'],data_type='D')

	s = Simulator()
	s.add_strategy(r)
	s.run(d)

	s.write('rtr_100_10_20')

	s.show()
