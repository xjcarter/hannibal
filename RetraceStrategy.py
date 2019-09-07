
from Strategy import StrategyBase
from MarketObjects import Order, IndicatorMap
from Indicators import TimeSeries

'''
RetraceStrategy:
using SMA as a long/short filter, 
go long when momentum moves from negative to positive, (close > SMA)
go short when momentum move from positive to negative, (close < SMA)

average = length of simple moving average
momentum = length of simple momentum filter
duration = holding period of the trade
'''

class RetraceStrategy(StrategyBase):
    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(RetraceStrategy,self).__init__(name,strategy_setup,strategy_params)

        self.bar_interval = 0 

        ## Indicator map takes a list of indicator definitions:
        ## (local_name, class_name, kwargs for class_name(**kwargs) constructor)

        indicators = [
            dict(name='momentum', class_name='MO', kwargs=dict(length=strategy_params['momentum'])),
            dict(name='average', class_name='SMA', kwargs=dict(length=strategy_params['average'])),
            dict(name='duration', class_name='TimeSeries', kwargs=dict(capacity=strategy_params['duration']))
        ]

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
            m_avg = self.indicator_map[symbol]['average']
            duration = self.indicator_map[symbol]['duration']

            self.log.debug('pushing: %s  close= %s' % (symbol, price_data.close))
            momentum.push(price_data.close)
            m_avg.push(price_data.close)

            if not opens:

                if pos == None or pos.qty == 0:
                    if momentum.size() > 1 and m_avg.size() > 1:
                        ## mo = tuple(pt momentum, pct momentum)
                        p_value = momentum[0][0]
                        y_value = momentum[1][0]
                        self.log.debug('%s indicator time: %s' % (symbol, price_data.timestamp))
                        if p_value > 0 and y_value <= 0 and price_data.close > m_avg[1]:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__BUY %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.BUY,qty,Order.MARKET,None,None))
                            ## clear the historical price counter
                            duration.reset()
                        if p_value <  0 and y_value >= 0 and price_data.close < m_avg[1]:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__SHORT %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.SELL,qty,Order.MARKET,None,None))
                            ## clear the historical price counter
                            duration.reset()

                elif pos.qty > 0:
                    ## keep track of time we have been in the trade
                    duration.push(price_data.close)
                    if duration.size() >= duration.capacity:
                        self.log.debug("__SELL LONG %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.SELL,pos.qty,Order.MARKET,None,None))

                elif pos.qty < 0:
                    ## keep track of time we have been in the trade
                    duration.push(price_data.close)
                    if duration.size() >= duration.capacity:
                        self.log.debug("__COVER SHORT %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.BUY,abs(pos.qty),Order.MARKET,None,None))

            if self.capture_data:
                moo = None
                if momentum.size() > 0: moo = momentum[0][0]
                snapshot = dict(date=price_data.timestamp, close=price_data.close, average=m_avg[0], momentum=moo, duration=duration[0])
                self.time_series.push(snapshot)


