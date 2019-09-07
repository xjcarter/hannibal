
from DataQueues import DQueue, DataLatch
from Exchange import Exchange
from Portfolio import Portfolio
from DataFeed import DataFeed
import logging
import sys
import datetime
import math
from collections import OrderedDict
from prettytable import PrettyTable
import matplotlib.pylab as pylab
import pandas

'''
Simulator is the base event simulator module
it requires a strategy, and data source
you add add multiple strategies to the simulator using add_strategy()
output can be ploted using the show() method, and saved using write()
Example:
    >> r = RetraceStrategy(name='strategy_name',strategy_params=dict(average=150,duration=20,momentum=65))
    >> d = DataFeedList(['SPY.csv'],data_type='D')

    >> s = Simulator()
    >> s.add_strategy(r)
    >> s.run(d)
    >> s.write('simulation1')   ## creates pickle and xls dumps

'''

# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s | %(name)-25s | %(levelname)-9s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='simulator.log',
                    filemode='w')

log = logging.getLogger('Simulator')
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)

## setup for better looking graphs
pandas.options.display.mpl_style = 'default'
pylab.rcParams['figure.figsize'] = 10, 8

'''
Scoring Functions for evaluting simulation results
'''

##  standard fitness function 
def fitness_function(score_input,min_trades=1):
    '''
    score_input:
    {
     'avg_dd': 8.668810289387675,
     'cnt': 7,
     'l_avg': -8.666666666666837,
     'l_std': 3.51188458428321,
     'max_dd': 17.99999999999926,
     'max_equ': 43.99999999999977,
     'mtm_pnl': 39.000000000000057,
     'pnl': -7.000000000000739,
     'shrp': -0.13130643285974053,
     'std_dd': 3.4530899952806187,
     'tag': 'portfolio_50',
     'w_avg': 4.749999999999943,
     'w_pct': 0.5714285714285714,
     'w_std': 2.2173557826073966
    }
    '''


    max_dd = score_input['max_dd']
    cnt = score_input['cnt']
    ## pnl = score_input['pnl']
    mtm_pnl = score_input['mtm_pnl']
    if pandas.isnull(mtm_pnl): mtm_pnl = 0

    ## fit_value = score_input['shrp']
     
    fit_value = 0
    if cnt != None and cnt >= min_trades:
        if max_dd != None and max_dd != 0:
            r = mtm_pnl/math.fabs(max_dd)
        else:
            r = math.sqrt(mtm_pnl)

        fit_value = (1-(1/math.sqrt(cnt))) * r

    return fit_value



class Simulator(object):
    def __init__(self):

        self.latch = None
        self.strategies = []
        self.portfolio = Portfolio('portfolio',None)
        self.exchange = Exchange()
        self.portfolio.IN_fills = self.exchange.OUT_fills

        self.stats = None

        self.verbose = True

        ## call on_EOD funcs at end of data file
        self.reset_on_EOD = True

        self.scoring_function = None


    def add_strategy(self,strategy):
        self.strategies.append(strategy)

        strategy.IN_fills = DQueue() 
        self.portfolio.add(strategy)
        self.exchange.add(strategy)


    def run(self,datafeed):

        log.info("reset_on_EOD = %s" % self.reset_on_EOD)

        self.latch = DataLatch(len(self.strategies)+2)
        self.portfolio.latch = self.latch
        self.exchange.latch = self.latch

        for s in self.strategies:
            s.latch = self.latch

        bg = datetime.datetime.now()
        if self.verbose: log.info('Sim Start: %s' % bg)

        for market_data in datafeed:
            if market_data != DataFeed.SENTINEL:
                self.latch.trap(market_data)
                ## ORDER MATTERS! 
                ## this allows submit-fill loop to happen in a single on_data() event
                for s in self.strategies:
                    s.on_data_sim(market_data)
                self.exchange.on_data_sim(market_data)
                self.portfolio.on_data_sim(market_data)
            else:
                if self.reset_on_EOD:
                    ## handle EOD processing
                    self.portfolio.on_EOD()
                    for s in self.strategies:
                        s.on_EOD()
                    self.exchange.on_EOD()

        nd = datetime.datetime.now()

        if self.verbose:
            log.info('Sim Completed: %s' % nd)
            log.info('Time Elapsed: %s' % (nd-bg))

        return self.dump()


    def dump(self):

        if not self.scoring_function:
            self.scoring_function = fitness_function

        if not self.stats:
            self.stats = self.portfolio.stats()

        self.stats['_score'] = self.scoring_function(self.stats)
        summary = OrderedDict()
        header = ['_score', 'cnt','w_pct','pr','pnl','mtm_pnl','max_equ','max_dd']
        for k in header:
            summary[k] = self.stats[k]

        table = PrettyTable(header)
        table.add_row(summary.values())
        header.pop(1)  ## remove 'cnt' label
        for k in header:
            table.float_format[k] = '0.2'

        if self.verbose: log.info('\n%s' % table)

        ## return stat summary for potential use elsewhere
        #return summary
        return self.stats


    ## show the equity curve
    def show(self):
        if not self.stats:
            self.stats = self.portfolio.stats()

        curve_df = self.portfolio.storage['curve']['portfolio']
        curve_df.plot(x='timestamp')


    ## write output
    def write(self,filename):

        root = ".".join(filename.split('.')[:-1])
        if not root: root = filename

        xls = ".".join([root,'xls'])
        pkl = ".".join([root,'pkl'])

        log.info('writing pickle file: %s' % pkl)
        self.portfolio.write(filename=pkl)

        self.portfolio.to_excel(filename=xls)




































