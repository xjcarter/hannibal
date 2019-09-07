

from Simulator import Simulator
from RetraceStrategy import RetraceStrategy
from DataFeed import DataFeedList


if __name__ == '__main__':

	r = RetraceStrategy('tiger',strategy_params=dict(average=150,duration=20,momentum=40))
	d = DataFeedList(['tiger_data.csv'],data_type='D')

	s = Simulator()
	s.add_strategy(r)
	s.run(d)

	s.write('tiger_150_20_40')

	s.show()
