
from Strategy import StrategyBase
from MarketObjects import Order, IndicatorMap, Position

'''
MPStrategy = Momentum Portfolio 
Take a universe of stocks ranked by momentum, and rebalance over a fixed duration
length = the momentum length used by each stock in the universe
duration = the duration the portfolio is rebalanced intraday
longs = number of longs to hold in the portfolio
shorts = number of shorts to hold in the portfolio
'''

class MPStrategy(StrategyBase):
    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(MPStrategy,self).__init__(name,strategy_setup,strategy_params)

        ## base config = general setup
        ## this can be in the form of an .ini file
        ## config = ConfigParser()
        ## config.read(base_config)
        ## config._sections  (is the dict form of ini file)
        ## or a dict 
        
        self.capital = 1000000.0 * 10 
        #self.bar_interval = 300  ## seconds 
        self.bar_interval = 0 

        ## in this case - since I have a single indicator
        ## strategy_params defines the parameters for the MO indicator 
        ## as defined in the Indicators.py module -
        #
        ## constructor for MO = MO(length=value) 
        ## - therefore strategy_params = dict(length=value)
        ## - i.e the MO indicator is constructed as MO(**strategy_params)

        ## Indicator map takes a list of indicator definitions:
        ## (local_name, clas_name, kwargs for class_name(**kwargs) constructor)
        indicators = [dict(name='momentum',class_name='MO', kwargs=dict(length=strategy_params['length']))]

        self.indicator_map = IndicatorMap(indicators)

        ## holds the long/short momentum portfolio
        self.portfolio = list()
        self.number_of_longs = strategy_params['longs']
        self.number_of_shorts = strategy_params['shorts']
        self.rebalance_count = 0
        self.rebalance_limit = int(strategy_params['duration'])



    def get_size(self,symbol,price):
        return 100

    def reset(self):
        self.indicator_map.reset()

    ## grab top momentum longs and bottom momentum shorts
    def rank_universe(self):

        ranks = []
        for symbol, indicators in self.indicator.iteritems():
            ## momentum return a series of tuples (mo, return)
            ## do ranking based on return
            mo_value = indicators['momentum'][1][0]
            if mo_value:
                ranks.append((mo_value,symbol))

        ## buy only longs with positive momentum
        ## sell only short with negative momentum
        ## this prevents sales in markets where he universe to completely bullish
        ## or buys when the market is completely bearish
        if ranks:
            ranks.sort()
            longs = [x for x in ranks[:self.number_of_longs] if x[0] > 0]
            shorts = [x for x in ranks[:-self.self.number_of_shorts] if x[0] < 0]
            return longs + shorts
        else:
            return []


    ## override this to implement strategy       
    def execute_on(self,price_book):

        self.log.debug("executing_on: %s: %s" % (price_book.last_timestamp, price_book.keys()))

        ## record current momentum values for all names in the universe
        for symbol in price_book.keys():
            price_data = price_book[symbol]

            momentum = self.indicator_map[symbol]['momentum']
            self.log.debug('pushing: %s  close= %s' % (symbol, price_data.close))
            momentum.push(price_data.close)


        rebalance = (self.rebalance_count == self.rebalance_limit)

        if not self.portfolio or rebalance:

            old_portfolio = self.portfolio[:]
            del self.portfolio[:]

            ## build new portfolio
            for mo_value, symbol in self.rank_universe():

                opens = self.open_orders(symbol)
                if not opens:
                    
                    pos = self.positions.get(symbol,Position(None,0,0))
                    curr = pos.qty
                    tgt = self.get_size(symbol,price_data.close)
                    if mo_value < 0: tgt = -tgt

                    self.log.debug("%s: current qty = %d, tgt = %d" % (symbol,curr,tgt))

                    qty = tgt - curr
                    if qty > 0:
                        self.log.debug("__BUY %s qty = %d" % (symbol,qty))
                        self.send_order(Order(self.name,symbol,Order.BUY,qty,Order.MARKET,None,None))
                    elif qty < 0:
                        qty = abs(qty)
                        self.log.debug("__SHORT %s qty = %d" % (symbol,qty))
                        self.send_order(Order(self.name,symbol,Order.SELL,qty,Order.MARKET,None,None))

                    self.portfolio.append(symbol)

            ## clean up positions not in the new portfolio
            remains = [x for x in old_portfolio if x not in self.portfolio]
            for symbol in remains:
                opens = self.open_orders(symbol)
                if not opens:
                    pos = self.positions.get(symbol,Position(None,0,0))
                    if pos.qty > 0:
                        self.log.debug("__EXIT_SELL %s qty = %d" % (symbol,qty))
                        self.send_order(Order(self.name,symbol,Order.SELL,qty,Order.MARKET,None,None))
                    elif pos.qty < 0:
                        self.log.debug("__EXIT_BUY %s qty = %d" % (symbol,qty))
                        self.send_order(Order(self.name,symbol,Order.BUY,abs(qty),Order.MARKET,None,None))

            self.rebalance_count = 0

        elif self.portfolio and not rebalance:
            ## count the periods to rebalance
            self.rebalance_count += 1

