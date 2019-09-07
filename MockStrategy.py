
import collections
import logging
import pprint
import pandas
from datetime import datetime
import sys
from MarketObjects import parse_date
from prettytable import PrettyTable


'''
MockStrategy is the daily trading strategy model used for simulating (output to a BlotterReport)
and generating next day orders (via OrderSheet)
the idea is to update daily market data, run the model, and examine the model output:
        - Blotter - the simulated buys/sells that the strategy should have done
        - OrderSheet - a listing of trading orders that should be sent for next day's trading
Inputs:
     - MockStrategy takes a price file (example: AAPL.daily.csv) - to drive trading strategy execution
     - and a transaction file (date, +/- captial. (example: 1900-01-01,initial_captial) to do init)
'''

Fill = collections.namedtuple('Fill',['date','symbol','qty','price'])

class BlotterReport(object):
    def __init__(self):
        self.blotter = list()

    def add(self,capital,fill):

        ## FIXME - t_cost and ending_capital are driven by functions... 
        t_cost = 0
        ending_capital = 0 

        r = collections.OrderedDict(starting_capital=capital,
                                    date=fill.date,
                                    symbol=fill.symbol,
                                    trade=fill.qty,
                                    price=fill.price,
                                    t_cost=t_cost,
                                    ending_capital=ending_capital)
        self.blotter.append(r)

    def to_csv(self,filename):
        try:
            df = pandas.DataFrame(self.blotter)
            if not df.empty:
                df.to_csv(filename)
        except Exception as e:
            print 'cannot dump blotter to %s' % filename
            print e

    def __repr__(self):
        p = None
        if self.blotter:
            columns = self.blotter[0].keys()
            p = PrettyTable(columns)
            for item in self.blotter:
                p.add_row(item.values())

        return p

    def __str__(self):
        return self.__repr__()



class OrderSheet(object):
    def __init__(self):
        self.order_sheet = list()

    def add(self,order):
        qty = order.signed_qty()
        price = order.limit_price if order.limit_price else order.stop_price
        r = collections.OrderedDict(date=qty.timestamp.strftime("%Y-%m-%d"),symbol=order.symbol,order_type=order.order_type,trade=qty,price=price)
        self.order_sheet.append(r)

    def to_csv(self,filename):
        try:
            df = pandas.DataFrame(self.order_sheet)
            if not df.empty:
                df.to_csv(filename)
        except Exception as e:
            print 'cannot dump order_sheet to %s' % filename
            print e

    def __repr__(self):
        p = None
        if self.order_sheet:
            columns = self.order_sheet[0].keys()
            p = PrettyTable(columns)
            for item in self.order_sheet:
                p.add_row(item.values())

        return p

    def __str__(self):
        return self.__repr__()




class MockStrategy(object):

    ## transaction date used to set initial capital (if in transaction file)
    SEED_DATE = '1900-01-01'

    def __init__(self, name, strategy_setup=None, strategy_params=None):

        tag = "%s [%s]" % (__name__,name)
        self.log = logging.getLogger(tag)
        self.log.addHandler(logging.StreamHandler(sys.stdout))
        self.log.setLevel(logging.INFO)

        ## strategy_setup =
        ## dict (or JSON object) that handles setup of strategy specific variables
        ## that need initialization SEPARATE from varying strategy parameters
        ## i.e. contract specifications, data bar_intervals, initial captial, etc
    
        self.strategy_setup = strategy_setup

        ## strategy_params =
        ## dict (or JSOM object) that holds variables driving strategy execution
        ## i.e.  indicator lengths, thresholds, holding durations, etc
        
        self.strategy_params = strategy_params

        if len(name) > 15: name = name[:15]
        self.name = name

        self.orders =  collections.defaultdict(list)  
        self.positions = {}
        self.transactions = {}

        self.blotter_report = BlotterReport()
        self.order_sheet = OrderSheet()

        ## trading size
        self.capital = 0 

        ## dictionary of fill processing funcs
        self.fill_funcs = dict(MOC=self._fill_MOC, MOO=self._fill_MOO, STP=self._fill_STOP, LMT=self._fill_LIMIT)


    '''
    fill functions - populate fill_func dictionary - and are called based on order_type
    '''

    def _fill_MOC(self,order,ohlc_data):
        return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=order.signed_qty(),price=ohlc_data['close'])

    def _fill_MOO(self,order,ohlc_data):
        return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=order.signed_qty(),price=ohlc_data['open'])

    def _fill_STOP(self,order,ohlc_data):
        qty = order.signed_qty()
        if qty < 0:
            ## sell stop
            if ohlc_data['open'] >= order.stop_price and ohlc_data['low'] <= order.stop_price:
                return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=qty,price=order.stop_price)
        else:
            ## buy stop
            if ohlc_data['open'] <= order.stop_price and ohlc_data['high'] >= order.stop_price:
                return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=qty,price=order.stop_price)
        return None

    def _fill_LIMIT(self,order,ohlc_data):
        qty = order.signed_qty()
        if qty < 0:
            ## sell limit
            if ohlc_data['open'] <= order.limit_price and ohlc_data['high'] >= order.limit_price:
                return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=qty,price=order.limit_price)
        else:
            ## buy limit
            if ohlc_data['open'] >= order.limit_price and ohlc_data['low'] <= order.limit_price:
                return Fill(date=ohlc_data['date'],symbol=ohlc_data['symbol'],qty=qty,price=order.limit_price)
        return None


    def get_size(self, alloc, symbol, price):

        lot_size = 1
        units = 0
        base = price

        if base > 0:
            amt = int(alloc/base)
            if amt >= lot_size:
                units = int(amt/lot_size) * lot_size
            else:
                self.log.warning('%s: trading units too small: calc=%d, min=%d' % (symbol,amt,lot_size))
        else:
            self.log.warning('%s: zero risk base, no units allocated' % symbol)

        return units


    def send_order(self,order):
        self.orders[order.symbol].append(order)

    def fill_order(self,order,ohlc_data):
        def _null(order,ohlc_data):
            return None

        f = self.fill_funcs.get(order.order_type,_null)
        return f(order,ohlc_data)

    def add_capital(self,date,amount):
        dt = None
        if isinstance(date,datetime):
            dt = date.strftime('%Y-%m-%d')
        else:
            dt = parse_date(date).strftime('%Y-%m-%d')

        if dt != None:
            self.transactions[dt] = amount
            self.log.info('added transaction: date= %s, amt= %f' % (dt,amount))
            if MockStrategy.SEED_DATE in self.transactions:
                self.capital = self.transactions[MockStrategy.SEED_DATE]
                self.log.info('initializing capital = %.2f' % self.capital)
        else:
            self.log.warning('could not add transaction: date= %s amt= %s' % (date,amount))


    ## data_feed = price data to drive strategy
    ## transaction_file = times series recording additions and withdrawls of trading capital
    ##    ex: 1900-01-01, initial_capital
    ##        2015-06-01, -10000
    def run(self,data_feed,transaction_file):

        try:
            df = pandas.read_csv(transaction_file)
            dates = [parse_date(x).strftime('%Y-%m-%d') for x in df['date'].tolist()]
            trax = [float(x) for x in df['transaction'].tolist()]
            self.log.info('loading transactions %s' % transaction_file)
            self.transactions = dict(zip(dates,trax))
            if MockStrategy.SEED_DATE in self.transactions:
                self.capital = self.transactions[MockStrategy.SEED_DATE]
                self.log.info('initializing capital = %.2f' % self.capital)
        except Exception as e:
            self.log.info('cannot read transaction_file: %' % transaction_file)
            self.log.info(e) 

        try:
            df = pandas.read_csv(data_feed)
            df['date'] = df['date'].map(lambda x:parse_date(x).strftime('%Y-%m-%d'))
            self.log.info('running strategy: %s, data_feed: %s' % (self.name,data_feed))
            self.run_strategy(df)
        except Exception as e:
            self.log.info('cannot read data_file: %s' % data_feed)
            self.log.info(e)


    def run_strategy(self,data):
        data = data.sort(['date'], ascending=['True'])
        ## bundle data by date
        daily_data = dict(list(data.groupby('date')))
        for date, daily_bundle in daily_data.iteritems():
            
            ## add/withdrawl any cash indicated by the transaction file for that date
            adjustment = self.transacations.get(date,0)
            if adjustment != 0:
                new_cash = self.capital + adjustment
                cash_tuple = (date,self.capital,adjustment,new_cash)
                self.log.info('adjusting capitial: %s  start = %.2f, adj = %.2f, capital= %2.f' % (cash_tuple))
                self.capital = new_cash

            ## run model each individual symbol entry in the bundle
            ## each bundle, (for a given date):
            ##    symbol, open, high, low, close
            ##    AAPL    ..    ..     ..    ..
            ##    SPY     ..    ..     ..    ..
            
            for i, ohlc_data in daily_bundle.iterrows():
                self.calc_analytics(date, ohlc_data)
                if self.open_orders(ohlc_data['symbol']):
                    self.process_orders(date, ohlc_data)
                else:
                    self.check_strategy(date, ohlc_data)

    def process_orders(self,date,ohlc_data):
        ## update positions
        ## and post simulated fills to BlotterReport
        for order in self.orders.get(ohlc_data['symbol'],[]):
            fill = self.fill_order(order,ohlc_data)
            if fill:
                self.blotter_report.add(self.capital,fill)

    '''
    override in strategy to be implemented:
    calc_analytics - do any indicator calcs (use a IndicatorMap object)
    check_strategy - execution logic: 1. check positions, evaluate analytics, call send_orders()
    '''
    
    def calc_analytics(self,date,ohlc_data):
        ## calc analytics
        raise NotImplementedError

    def check_strategy(self,date,ohlc_data):
        ## step thru strategy logic
        raise NotImplementedError

 
    def __repr__(self):
        setup = "strategy_setup = %s" % pprint.pformat(self.strategy_setup)
        params = "strategy_params = %s" % pprint.pformat(self.strategy_params)
        return "\n".join([setup,params])

    def __str__(self):
        return self.__repr__()

            












