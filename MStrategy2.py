
from Strategy import StrategyBase
from MarketObjects import Order, IndicatorMap
from Indicators import TimeSeries

class MStrategy2(StrategyBase):
    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(MStrategy2,self).__init__(name,strategy_setup,strategy_params)

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
        indicators = [dict(name='momentum',class_name='MO', kwargs=dict(length=strategy_params['length'])),
                        dict(name='duration',class_name='TimeSeries', kwargs=dict(capacity=strategy_params['duration']))]

        self.indicator_map = IndicatorMap(indicators)

        self.capture_data = False
        self.time_series = TimeSeries()


    def get_size(self,symbol,price):
        return 100

    def reset(self):
        self.indicator_map.reset()

    def dump_data(self):
        if self.capture_data:
            import pandas
            if self.time_series.series:
                return pandas.DataFrame(list(self.time_series.series.reverse()))
            else:
                return None
        else:
            print "capture_data = False. nothing captured"

    ## override this to implement strategy       
    def execute_on(self,price_book):

        self.log.debug("executing_on: %s: %s" % (price_book.last_timestamp, price_book.keys()))

        for symbol in price_book.keys():
            price_data = price_book[symbol]

            ## pos  = Position(symbol,qty,price)
            ## pos == None: no activity in this symbol yet
            pos = self.positions.get(symbol,None)

            opens = self.open_orders(symbol)

            momentum = self.indicator_map[symbol]['momentum']
            duration = self.indicator_map[symbol]['duration']

            self.log.debug('pushing: %s  close= %s' % (symbol, price_data.close))
            momentum.push(price_data.close)
            duration.push(price_data.close)

            if momentum.size() > 0:
                self.log.debug("MO= %f" % momentum[0][0])
            if duration.size() > 0:
                self.log.debug("Duration= %d" % duration.size())

            if not opens:

                if pos == None or pos.qty == 0:
                    if momentum.size() > 1:
                        ## mo = tuple(pt momentum, pct momentum)
                        p_value = momentum[0][0]
                        y_value = momentum[1][0]
                        self.log.debug('%s indicator time: %s' % (symbol, price_data.timestamp))
                        if p_value > 0 and y_value <= 0:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__BUY %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.BUY,qty,Order.MARKET,None,None))
                            duration.reset()
                        if p_value <  0 and y_value >= 0:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__SHORT %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.SELL,qty,Order.MARKET,None,None))
                            duration.reset()

                elif pos.qty > 0:
                    if duration.size() >= duration.capacity:
                        self.log.debug("__SELL LONG %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.SELL,pos.qty,Order.MARKET,None,None))

                elif pos.qty < 0:
                    if duration.size() >= duration.capacity:
                        self.log.debug("__COVER SHORT %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.BUY,abs(pos.qty),Order.MARKET,None,None))


            if self.capture_data:
                moo = None
                if momentum.size() > 0: moo = momentum[0][0]
                snapshot = dict(date=price_data.timestamp, close=price_data.close, momentum=moo, duration=duration[0])
                self.time_series.push(snapshot)
