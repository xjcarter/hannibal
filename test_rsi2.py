

from RSIStrategy import RSIStrategy 
from DataFeed import DataFeedList
from Optimizer import Optimizer
from Simulator import Simulator
from datetime import datetime



def optimize():

    optimizer = Optimizer()
    optimizer.strategy_class = RSIStrategy
    #optimizer.data_feed = DataFeedList(['20081210.SPY.1m.csv','20081211.SPY.1min.csv','20081212.SPY.1min.csv'],data_type='B') 
    #optimizer.data_feed = DataFeedList(['20081210.SPY.30s.csv','20081211.SPY.30s.csv','20081212.SPY.30s.csv'],data_type='I') 
    optimizer.data_feed = DataFeedList(['SPY.csv'],data_type='D') 

    ## set population size
    optimizer.size = 40 
    optimizer.max_generations = 50
    optimizer.outfile = '%s_%s.xls' % (__file__[:-3],datetime.now().strftime("%Y%m%d"))
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
    optimizer.add_parameter(dict(name='average',min_val=20,max_val=200,steps=64,converter=int))
    optimizer.add_parameter(dict(name='duration',min_val=5,max_val=20,steps=8,converter=int))

    optimizer.run()

def simulate():

    '''
    strategy_params=dict(top=60,btm=40,rsi=14,average=111,duration=5))
    +--------+-----+-------+------+---------+---------+---------+---------+
    | _score | cnt | w_pct |  pr  |   pnl   | mtm_pnl | max_equ |  max_dd |
    +--------+-----+-------+------+---------+---------+---------+---------+
    |  5.70  |  97 |  0.61 | 1.25 | 7163.57 | 7163.57 | 7608.81 | 1129.33 |
    +--------+-----+-------+------+---------+---------+---------+---------+
    equity curve = 570x.png

    strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))
    +--------+-----+-------+------+----------+----------+----------+---------+
    | _score | cnt | w_pct |  pr  |   pnl    | mtm_pnl  | max_equ  |  max_dd |
    +--------+-----+-------+------+----------+----------+----------+---------+
    |  7.56  | 106 |  0.67 | 1.22 | 11139.79 | 11139.79 | 11158.79 | 1330.16 |
    +--------+-----+-------+------+----------+----------+----------+---------+
    equity curve = 756x.png
    '''

    m = RSIStrategy(name='rsi2_spy',strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))

    s = Simulator()
    s.add_strategy(m)
    s.run(DataFeedList(['SPY.csv'],data_type='D'))

    s.write('rsi2_SPY_%s' % datetime.now().strftime("%Y%m%d"))


def simulate_AAPL():

    m = RSIStrategy(name='rsi2_aapl',strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))

    s = Simulator()
    s.add_strategy(m)
    s.run(DataFeedList(['AAPL.csv'],data_type='D'))

    s.write('rsi2_AAPL_%s' % datetime.now().strftime("%Y%m%d"))


"""
test the consisitency of multiple files and composite files
the same data in different input streams should give the same outputs
"""


def simulate_AAPL_SPY():

    m = RSIStrategy(name='rsi2_aapl_spy',strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))

    s = Simulator()
    s.add_strategy(m)
    s.run(DataFeedList(['AAPL.csv','SPY.csv'],data_type='D'))

    s.write('rsi2_AAPL_SPY_%s' % datetime.now().strftime("%Y%m%d"))

def simulate_SPY_AAPL():

    m = RSIStrategy(name='rsi2_spy_aapl',strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))

    s = Simulator()
    s.add_strategy(m)
    s.run(DataFeedList(['SPY.csv','AAPL.csv'],data_type='D'))

    s.write('rsi2_SPY_AAPL_%s' % datetime.now().strftime("%Y%m%d"))

def simulate_SPY_AAPL_composite():

    '''
    test to make sure that a composite file (AAPL and SPY combined)
    is the same as the individuals (AAPL.csv and SPY.csv separately) 
    '''

    m = RSIStrategy(name='rsi2_spy_v_aapl',strategy_params=dict(top=60,btm=40,rsi=12,average=180,duration=7))

    s = Simulator()
    s.add_strategy(m)
    s.run(DataFeedList(['SPY_AAPL.csv'],data_type='D'))

    s.write('rsi2_SPYvAAPL_%s' % datetime.now().strftime("%Y%m%d"))

if __name__ == '__main__':
    #optimize()
    #simulate()
    #simulate_AAPL()
    #simulate_AAPL_SPY()
    simulate_SPY_AAPL_composite()


































