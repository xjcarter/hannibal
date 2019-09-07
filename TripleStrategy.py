
from Strategy import StrategyBase
from MarketObjects import Order, IndicatorMap

'''
Triple Momentum Strategy 
used to test 2-point crossover optimizer
'''

class TripleStrategy(StrategyBase):
    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(TripleStrategy,self).__init__(name,strategy_setup,strategy_params)

        self.bar_interval = 1 ## seconds 

        ## parameter space to search over
        ## mo1 = short term momentum crossover 
        ## mo2 = medium term mo filter 
        ## mo3 = long term mo filter 
        ## duration = trade holding period
       
        params = strategy_params 

        indicators = [  dict(name='mo1',class_name='MO',kwargs=dict(length=params['mo1'])),
                        dict(name='mo2',class_name='MO',kwargs=dict(length=params['mo2'])),
                        dict(name='mo3',class_name='MO',kwargs=dict(length=params['mo3'])),
                        dict(name='duration',class_name='TimeSeries',kwargs=dict(capacity=params['duration']))
                    ]
         
        self.indicator_map = IndicatorMap(indicators)

    def get_size(self,symbol,price):
        return 100

    ## override this to implement strategy       
    def execute_on(self,price_book):

        self.log.debug("executing_on: %s: %s" % (price_book.last_timestamp, price_book.keys()))

        for symbol in price_book.keys():
            price_data = price_book[symbol]

            ## pos  = Position(symbol,qty,price)
            ## pos == None: no activity in this symbol yet
            pos = self.positions.get(symbol,None)

            opens = self.open_orders(symbol)

            mo1 = self.indicator_map[symbol]['mo1']
            mo2 = self.indicator_map[symbol]['mo2']
            mo3 = self.indicator_map[symbol]['mo3']
            duration = self.indicator_map[symbol]['duration']

            self.log.debug('pushing: %s  close= %s' % (symbol, price_data.close))
            mo1.push(price_data.close)
            mo2.push(price_data.close)
            mo3.push(price_data.close)

            if not opens:

                if pos == None or pos.qty == 0:
                    if mo1.size() > 1 and mo2.size() > 0 and mo3.size():
                        ## mo = tuple(pt momentum, pct momentum)
                        p_value = mo1[0][0]
                        y_value = mo1[1][0]
                        self.log.debug('%s indicator time: %s' % (symbol, price_data.timestamp))
                        if p_value > 0 and y_value <= 0 and mo2[0] > 0 and mo3[0] > 0:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__BUY %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.BUY,qty,Order.MARKET,None,None))
                            ## clear the historical price counter
                            duration.reset()
                        if p_value <  0 and y_value >= 0 and mo2[0] < 0 and mo3[0] < 0:
                            qty = self.get_size(symbol,price_data.close)
                            self.log.debug("__SHORT %s qty = %d" % (symbol,qty))
                            if qty: self.send_order(Order(self.name,symbol,Order.SELL,qty,Order.MARKET,None,None))
                            ## clear the historical price counter
                            duration.reset()

                elif pos.qty > 0:
                    ## keep track of time we have been in the trade
                    ## exit after holding period or mid term momentum turns negative
                    duration.push(price_data.close)
                    if duration.size() >= duration.capacity or mo2[0] < 0:
                        self.log.debug("__SELL LONG %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.SELL,pos.qty,Order.MARKET,None,None))

                elif pos.qty < 0:
                    ## keep track of time we have been in the trade
                    ## exit after holding period or mid term momentum turns positive 
                    duration.push(price_data.close)
                    if duration.size() >= duration.capacity or mo2[0] > 0:
                        self.log.debug("__COVER SHORT %s qty = %d" % (symbol,pos.qty))
                        self.send_order(Order(self.name,symbol,Order.BUY,abs(pos.qty),Order.MARKET,None,None))
