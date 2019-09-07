
from MarketObjects import Order, Fill
from DataQueues import OrderHandler, FillHandler
from threading import Thread, Lock
import collections
import logging

class Exchange(Thread):

    def __init__(self):

        super(Exchange,self).__init__()

        self.IN_orders = OrderHandler() 
        self.OUT_fills = FillHandler() 
        self.latch = None 
        self.lock = Lock()
        self.running = True
        self.order_book = collections.defaultdict(list)

        self.current_timestamp = None

        ## dictionary of last recv'd market data object
        ## per symbol.
        self.current_data = {}

        self.log = logging.getLogger(__name__)

    ##NOTE that add() takes something that looks like the strategy
    ##an interface that provides the name and queue connecitions for the strategy
    ##this allow distributed placement of actual strategies
    def add(self,strategy):

        self.IN_orders.add_queue(strategy.OUT_orders.new(),strategy.name)
        self.OUT_fills.add_queue(strategy.IN_fills,strategy.name)

    def market_order(self,price_data, order):
        fill = None
        ts = price_data.timestamp
        if order.side == Order.BUY:
            fill_amt = order.qty
            if price_data.ask:
                fill_price = price_data.ask
                if price_data.ask_volume:
                    if price_data.ask_volume < order.qty:
                        fill_amt = price_data.ask_volume
                        ## adjust order amt exchange needs to fill
                        order.qty -= fill_amt
            else:
                fill_price = price_data.close
                if price_data.trade_volume < order.qty:
                    fill_amt = price_data.trade_volume
                    ## adjust order amt exchange needs to fill
                    order.qty -= fill_amt

            fill = Fill(order.symbol,fill_price,fill_amt,order.side,ts,order.order_id)

        if order.side == Order.SELL:
            fill_amt = order.qty
            if price_data.bid:
                fill_price = price_data.bid
                if price_data.bid_volume:
                    if price_data.bid_volume < order.qty:
                        fill_amt = price_data.bid_volume
                        ## adjust order amt exchange needs to fill
                        order.qty -= fill_amt
            else:
                fill_price = price_data.close
                if price_data.trade_volume < order.qty:
                    fill_amt = price_data.trade_volume
                    ## adjust order amt exchange needs to fill
                    order.qty -= fill_amt

            fill = Fill(order.symbol,fill_price,fill_amt,order.side,ts,order.order_id)

        return fill


    #TODO - finish order types

    def stop_order(price_data, order):
        pass

    def limit_order(price_data, order):
        pass

    def fill_order(self, order, price_data):
        fill = None
        if order.timestamp <= price_data.timestamp:
            if order.order_type == Order.MARKET:
                fill = self.market_order(price_data, order)
            elif order.order_type == Order.STOP:
                fill = self.stop_order(price_data, order)
            elif order.order_type == Order.STOP_LIMIT:
                fill = self.stop_order(price_data, order)
            elif order.order_type == Order.LIMIT:
                fill = self.limit_order(price_data, order)

            if fill: self.adjust_book(fill)

        return fill

    def adjust_book(self,fill):
        orders = self.order_book[fill.symbol]
        for order in orders:
            if order.order_id == fill.order_id:
                if fill.qty >= order.qty:
                    orders.remove(order)
                    break


    def process_orders(self, market_data):
        fills = collections.defaultdict(list)
        for symbol, orders in self.order_book.iteritems():
            if market_data.symbol == symbol:
                self.log.info("checking: %s" % symbol)
                for order in orders:
                    fill = self.fill_order(order, market_data)
                    if fill:
                        self.OUT_fills.put(fill,order.owner)
                        #self.OUT_fills.put(copy.deepcopy(fill))
                        fills[symbol].append(fill)
                        self.log.info("fill: %s" % fill)

        for symbol in fills.keys():
            self.log.info("fills(%s) = %d" % (symbol,len(fills[symbol])))

            ## no more orders for that symbol outstanding
            ## remove the key from the map
            if len(self.order_book[symbol]) == 0:
                del self.order_book[symbol]


    def add_order(self, new_order):
        orders = self.order_book[new_order.symbol]

        ## sort by timestamp
        orders.append(new_order)
        #orders.append(copy.deepcopy(new_order))
        self.log.info("add_order: %s" % new_order)
        if len(orders) > 1:
            j = [ (x.timestamp,x) for x in orders ]
            j.sort()
            self.order_book[new_order.symbol] = [ x[1] for x in j ]


    def shutdown(self):
        self.log.info('Exchange Thread Stopped.')
        self.running = False


    def run(self):

        while self.running:

            ### grab new orders from the portfolio
            with self.lock:
                try:
                    new_order = self.IN_orders.get()
                    self.add_order(new_order)
                except IndexError:
                    ## fail thru if no data to grab
                    pass

    def on_data(self,market_data):

        if market_data:

            with self.lock:

                self.current_timestamp = market_data.timestamp

                while self.IN_orders:
                    new_order = self.IN_orders.get()
                    self.add_order(new_order)

                self.current_data[market_data.symbol] = market_data
                self.log.info("LIVE_DATA: %s" % market_data)
                ## returns a dict: fills[symbol] = [list of fills]
                self.process_orders(market_data)
                self.latch.notify()


    def on_data_sim(self,market_data):

        if market_data:

            self.current_timestamp = market_data.timestamp

            while self.IN_orders:
                new_order = self.IN_orders.get()
                self.add_order(new_order)

            self.current_data[market_data.symbol] = market_data
            self.log.info("SIM_DATA: %s" % market_data)
            ## returns a dict: fills[symbol] = [list of fills]
            self.process_orders(market_data)

            self.latch.notify()



    def on_EOD(self):

        self.log.info("reset on EOD")
        with self.lock:
            self.IN_orders.clear()
            self.OUT_fills.clear()
            self.current_data = {}
            self.order_book = collections.defaultdict(list)




