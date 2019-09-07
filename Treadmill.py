
## run multiple tests for a single simulation
## and records the variation between runs

from collections import defaultdict
from prettytable import PrettyTable
import logging
import sys
from Simulator import Simulator
from Simulator import fitness_function 
import cPickle
import random, string
import pandas


log = logging.getLogger('Treadmill')
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)

'''
Treadmill is a simulation engine class that runs the same simulation over a fixed number 
of iterations.

The purpose is to determine the 'most likely' result of the strategies run in hannibal's
threaded environment.  Because of the queued/async order submmit-order filled logic, all
trading is not completed deterministic.

The Treadmill evaluates complete set of simulations run (default run count=50) and looks
at the grouping and dispersion of the results. The more identical run the better, and a
dispersion reading (DSP) of under 5% shows stability.  DSP is measure a pct ratio of the 
results standard deviation of pnl to the average pnl of all runs

In [10]: from Treadmill import Treadmill

In [11]: t = Treadmill()

In [12]: t.strategy_class = RetraceStrategy

In [13]: t.strategy_params=dict(average=150,duration=20,momentum=65)

In [14]: t.data_feed = DataFeedList(['SPY.csv'],data_type='D')

In [15]: t.run()

'''

class Treadmill(object):

    def __init__(self):
        self.strategy_class = None 
        self.strategy_params = None
        self.strategy_setup = None
        self.data_feed = None

        self.record = defaultdict(int)

        self.best = None
        self.shelf = {} 
        self.df_out = None

        ## flag Simulator to run EOD calls
        self.reset_on_EOD = True 

    def _tempname(self):
        return "".join([random.choice(string.ascii_uppercase) for i in range(3)])

    def run(self,count=50):
        log.info('strategy: %s' % self.strategy_class.__name__)
        log.info('strategy_params: %s' % self.strategy_params)

        self.best = None
        self.shelf = {} 

        for i in xrange(count):
            s = Simulator()
            s.reset_on_EOD = self.reset_on_EOD
            name = '%s_%s' % (self.strategy_class.__name__, self._tempname())
            s.add_strategy(self.strategy_class(name,strategy_setup=self.strategy_setup,strategy_params=self.strategy_params))
            self.data_feed.reset()
            log.info('\n%d/%d\nStart Strategy= %s' % (i+1,count,name))
            summary = s.run(self.data_feed)
            log.info('End Strategy= %s' % name)
            key = (summary['cnt'],summary['pnl'],summary['mtm_pnl'],summary['max_dd'])
            self.record[key] += 1
            if not self.best or (self.record[key] >= self.best[1]):
                self.best = (key,self.record[key],name)

            self.shelf[key] = s.portfolio.storage

        group = []
        columns = ['score','cnt','trades','pnl','mtm_pnl','max_dd']
        p = PrettyTable(columns)
        for k,v in self.record.iteritems():
            u = dict(cnt=k[0],mtm_pnl=k[2],max_dd=k[3])
            score = fitness_function(u)
            u.update({'score':score,'trades':k[0],'pnl':k[1]})
            group.append(u)
            p.add_row([score,v,k[0],k[1],k[2],k[3]])

        ## tack on summary information
        df = pandas.DataFrame(group)
        means = []
        devs = []
        for c in columns:
            if c in ['score', 'pnl','mtm_pnl', 'max_dd']:
                p.float_format[c] = '0.2'
                p.align[c] = 'r'
                m = df[c].mean()
                means.append(m)
                ## calc % of dispersion relative to avg pnl
                devs.append(df[c].std()/m)
            elif c in ['trades']:
                means.append(' ')
                devs.append(' ')
            else:
                means.append('AVG')
                devs.append('DSP')
        p.add_row(means)
        p.add_row(devs)

        log.info('\n%s' % p)
        log.info('Best Simulation: Strategy= %s' % self.best[2]) 


        ## return dataframe - just in case you want further analysis
        self.df_out = df


    def write(self,filename=None):
        ## NOTE: if cPickle has trouble with the dict() of DataFrames
        ## try using the 'dill' module.
       
        ## use best run tagname as default 
        if not filename: filename = self.best[2]
        
        root = ".".join(filename.split('.')[:-1])
        if not root: root = filename
        filename = "".join([root,'.pkl'])

        try:
            log.info("Writing output file: %s" % filename)
            key = self.best[0]
            with open(filename, 'wb') as pickle_file:
                cPickle.dump(self.shelf[key],pickle_file)
        except Exception as e:
            log.error("Unable to write output file: '%s' for treadmill" % filename)
            log.error(type(e))









































