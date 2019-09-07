
from Strategy import StrategyBase
from MarketObjects import Order, IndicatorMap
from Indicators import TimeSeries

''' 
RSI oscillator strategy 
rsi = length of the RSI indicator, top & btm = sell / buy thresholds as int (0 -100)
duration = holding period of the trade
average (optional) = length of simple moving average as a trend filter
'''

class RSIStrategy(StrategyBase):
    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(RSIStrategy,self).__init__(name,strategy_setup,strategy_params)

        ## base config = general setup
        ## this can be in the form of an .ini file
        ## config = ConfigParser()
        ## config.read(base_config)
        ## config._sections  (is the dict form of ini file)
        ## or a dict 
        
        self.capital = 1000000.0 * 10 
        ## self.bar_interval is used for aggregating tick data into bars (specifically if the strategy is
        ##      to handle real-time, tick by tick feeds...)
        ## bar_interval = 0, means take each data element on its own, do data aggregation is to occur 
        self.bar_interval = 0 


        ## threshold overbought/oversold levels as integers (0-100)
        self.top = strategy_params['top']/100.0
        self.btm = strategy_params['btm']/100.0

        ## Indicator map takes a list of indicator definitions:
        ## (local_name, clas_name, kwargs for class_name(**kwargs) constructor)
        indicators = [dict(name='rsi',class_name='RSI', kwargs=dict(length=strategy_params['rsi'])),
                        dict(name='duration',class_name='TimeSeries', kwargs=dict(capacity=strategy_params['duration']))]

        ## optional moving average filter
        if 'average' in strategy_params:
            indicators.append(dict(name='average',class_name='SMA',kwargs=dict(length=strategy_params['average'])))

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

        for symbol in price_book:
            price_data = price_book[symbol]

            ## pos  = Position(symbol,qty,price)
            ## pos == None: no activity in this symbol yet
            pos = self.positions.get(symbol,None)

            opens = self.open_orders(symbol)

            rsi = self.indicator_map[symbol]['rsi']
            duration = self.indicator_map[symbol]['duration']
            self.log.debug('pushing: %s  close= %s' % (symbol, price_data.close))

            px = (price_data.high + price_data.low + price_data.close)/3.0 
            rsi.push(px)
            duration.push(px)

            ## use trend filter if given
            trend_up = trend_down = True
            average = self.indicator_map[symbol].get('average',None)
            if average: 
                average.push(px)
                if average.size() > 1:
                    if px > average[1]:
                        trend_down = False
                    else:
                        trend_up = False

            if rsi.size() > 0:
                self.log.debug("RSI= %f" % rsi[0])
            if average and average.size() > 0:
                self.log.debug("AVG= %f" % average[0])
            if duration.size() > 0:
                self.log.debug("Duration= %d" % duration.size())


            if not opens:

                if pos == None or pos.qty == 0:
                    if rsi.size() > 1:
                        ## mo = tuple(pt momentum, pct momentum)
                        p_value = rsi[0]
                        y_value = rsi[1]
                        self.log.debug('%s indicator time: %s' % (symbol, price_data.timestamp))
                        if p_value > y_value and y_value <= self.btm and trend_up:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__BUY %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.BUY,qty,Order.MARKET,None,None))
                            duration.reset()
                        if p_value < y_value and y_value >= self.top and trend_down:
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
                ## x = y = None
                ## if rsi.size() > 0: x = rsi[0]
                ## if average and average.size() > 0: y = average[0]
                snapshot = dict(date=price_data.timestamp, close=price_data.close, avp=px, rsi=rsi[0], avg=average[0], duration=duration[0])
                self.time_series.push(snapshot)
