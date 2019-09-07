
from DataQueues import DQueue, DataLatch
from Exchange import Exchange
from Portfolio import Portfolio
from DataFeed import DataFeedBars, DataFeedDaily
from MStrategy import MStrategy
from RetraceStrategy import RetraceStrategy
from TripleStrategy import TripleStrategy
from Optimizer import Optimizer
import logging
import pprint

# turn off all logging outside optimizer 
# set level = CRITICAL for the general config does this
logging.basicConfig(level=logging.CRITICAL,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='optimizer.log',
                    filemode='w')

# set the optimizer logger to DEBUG
# and additionally dump optimizer output to the console
# 'Optimizer' logger tag is defined in the Optimizer module
log = logging.getLogger('Optimizer')

def test_strategy(strategy_params, run_id):

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strat_name = 'test_%04d' % run_id

    ## NOTE strategy_params is a dict that the strategy
    ## uses to initialize itself.
    strategy = MStrategy(strat_name,strategy_params=strategy_params)
    strategy.bar_interval = 1
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    porto_name = 'portfolio_%d' % run_id
    portfolio = Portfolio(porto_name,None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    simData = DataFeedBars('20100315.SPY.1m.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    return portfolio.stats()


def test_retrace_strategy(strategy_params, run_id):

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strat_name = 'test_%04d' % run_id

    ## NOTE strategy_params is a dict that the strategy
    ## uses to initialize itself.
    strategy = RetraceStrategy(strat_name,strategy_params=strategy_params)
    strategy.bar_interval = 1
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    porto_name = 'retrace_%d' % run_id
    portfolio = Portfolio(porto_name,None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    simData = DataFeedDaily('daily.SPY.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    return portfolio.stats()


def test_triple_strategy(strategy_params, run_id):

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strat_name = 'test_%04d' % run_id

    ## NOTE strategy_params is a dict that the strategy
    ## uses to initialize itself.
    strategy = TripleStrategy(strat_name,strategy_params=strategy_params)
    strategy.bar_interval = 1
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    porto_name = 'triple_%d' % run_id
    portfolio = Portfolio(porto_name,None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    simData = DataFeedDaily('daily.SPY.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    return portfolio.stats()



## test brute force test of a search set (no crossovers)
def test_optimizer():
    optimizer = Optimizer()
    run_id = 0

    optimizer.outfile = 'optimizer_out.xls'

    ## parameter space to search over
    optimizer.add_parameter(dict(name='length',min_val=100,max_val=200,steps=32,converter=int))


    while not optimizer.converged():
        params_set = optimizer.generate_set()
        for strategy_params in params_set:
            log.debug('Testing: %s' % pprint.pformat(strategy_params))
            sim_stats = test_strategy(strategy_params,run_id)
            optimizer.score(sim_stats,run_id)
            run_id += 1
        optimizer.dump()

    optimizer.write()


## test 1-point crossover of a search set
def test_optimizer2():
    optimizer = Optimizer()
    run_id = 0

    ## set population size
    optimizer.size = 40
    optimizer.max_generations = 5

    ## if not given: outfile will default to using the strategy name
    ## optimizer.outfile ='retrace_optimized.xls'

    ## parameter space to search over
    ## momentum = entry momentum crossover
    ## average = moving average filter
    ## duration = trade holding period
     
    param_list = [dict(name='momentum',min_val=10,max_val=100,steps=32,converter=int),
                  dict(name='average',min_val=20,max_val=200,steps=32,converter=int),
                  dict(name='duration',min_val=10,max_val=50,steps=16,converter=int) ]

    optimizer.add_parameters(param_list)

    while not optimizer.converged():
        params_set = optimizer.generate_set()
        for strategy_params in params_set:
            log.debug('Testing: %s' % pprint.pformat(strategy_params))
            sim_stats = test_retrace_strategy(strategy_params,run_id)
            optimizer.score(sim_stats,run_id)
            run_id += 1
        optimizer.dump()

    optimizer.write()


## test 2-point crossover of a search set
def test_optimizer3():
    optimizer = Optimizer()
    run_id = 0

    ## set population size
    optimizer.size = 40
    optimizer.max_generations = 5
    optimizer.outfile='triple_optimized.xls'

    ## parameter space to search over
    ## mo1 = short term momentum crossover 
    ## mo2 = medium term mo filter 
    ## mo3 = long term mo filter 
    ## duration = trade holding period
     
    param_list = [dict(name='mo1',min_val=5,max_val=50,steps=32,converter=int),
                  dict(name='mo2',min_val=60,max_val=100,steps=32,converter=int),
                  dict(name='mo3',min_val=110,max_val=200,steps=32,converter=int),
                  dict(name='duration',min_val=10,max_val=50,steps=16,converter=int) ]

    optimizer.add_parameters(param_list)

    while not optimizer.converged():
        params_set = optimizer.generate_set()
        for strategy_params in params_set:
            log.debug('Testing: %s' % pprint.pformat(strategy_params))
            sim_stats = test_triple_strategy(strategy_params,run_id)
            optimizer.score(sim_stats,run_id)
            run_id += 1
        optimizer.dump()

    optimizer.write()





if __name__ == "__main__":

    ## test brute force
    #test_optimizer()

    ## test 1-point crossover
    test_optimizer2()

    ## test 2-point crossover
    #test_optimizer3()































