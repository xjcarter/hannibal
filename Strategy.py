
import collections
from datetime import timedelta
from MarketObjects import Order, Fill, PriceBook, Position
import logging
from threading import Thread, Lock
from DataQueues import DQueue, OutQueue
import copy
import pprint

'''
Strategy is the base class that all strategies are to be derived from
The key methd that must be overriden is the execute_on() method
    def execute_on(price_book):
        takes a book of symbols at the current timestamp to operate over
        the method house the strategy execution logic
All support functionally: order submission, position accounting, end_of_day processing
are handled internally by Strategy class methods

The strategy communicate with outside world via data queues:
IN_fills is the queue handling incoming fills from the Portfolio object
OUT_orders houses all outgoing order sent via the send_order() methods
'''

## Proxy Interface for the Strategy to connect to a Portofolio
## object in a distributed environment
class StrategyInterface:

    def __init__(self, name, latch):
        self.name = name
        self.IN_fills = None
        self.OUT_orders = None
        self.lock = Lock()
        self.latch = latch

class StrategyBase(Thread):

    def __init__(self, name, strategy_setup=None, strategy_params=None):

        super(StrategyBase,self).__init__()

        tag = "$ %s" % name
        self.log = logging.getLogger(tag)

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

        self.target_timestamp = None
        self.current_timestamp = None

        self.IN_fills = None 
        self.OUT_orders = OutQueue() 
        self.IN_data = DQueue()
        self.latch = None
        self.lock = Lock()

        self.price_book = PriceBook()  # market data bucket
        self.current_data = None  # holds copy of last market data bucket
        self.start_up = True

        self.order_book = {}    ## dict[order_id]
        self.orders = []
        self.positions = {}
        self.trading_activity = collections.defaultdict(list)

        ## controls thread run()
        self.running = True

        ## trading size
        self.capital = 1000000.0 * 10 

        ## self.bar_interval is used for aggregating tick data into bars (specifically if the strategy is
        ##    to handle real-time, tick by tick feeds...)
        ## bar_interval = 0, means take each data element on its own, do data aggregation is to occur 
        ## self.bar_interval = 600  ## seconds 
        self.bar_interval = 0


    def get_size(self, symbol, price):

        lot_size = 1
        units = 0
        base = price

        if base > 0:
            amt = int(self.capital/base)
            if amt >= lot_size:
                units = int(amt/lot_size) * lot_size
            else:
                self.log.warning('%s: trading units too small: calc=%d, min=%d' % (symbol,amt,lot_size))
        else:
            self.log.warning('%s: zero risk base, no units allocated' % symbol)

        return units


    def open_orders(self,symbol):
        ## check if there are outstanding orders
        ## for a specific symbol
        return [ x for x in self.order_book.values() if x.symbol == symbol ]

    def send_order(self,order):
        order.stamp_time(self.current_timestamp)
        self.orders.append(order)
        self.order_book[order.order_id] = order

    def update_orders(self, fill):

        ## update outstanding orders
        self.log.info('updating orders (count=%d)' % len(self.order_book.values()))
        if fill.order_id in self.order_book.keys():
            self.order_book[fill.order_id].qty_left -= fill.qty
            if self.order_book[fill.order_id].qty_left == 0:
                self.log.info("rm filled order %s" % self.order_book[fill.order_id])
                del self.order_book[fill.order_id]
        else:
            self.log.error("fill= %s cannot find order_id %d" % (fill,fill.order_id))

        ## for logging purposes only
        self.log.info('remaining orders (count=%d)' % len(self.order_book.values()))
        open_symbols = set([x.symbol for x in self.order_book.values()])
        for symbol in open_symbols:
            opens = self.open_orders(symbol)
            for open_order in opens:
                self.log.info("open= %s" % open_order)

    def update_positions(self, fill):

        self.log.info("grab fill: %s" % fill)

        symbol = fill.symbol
        vqty = vwp = 0
        if symbol in self.positions.keys():
            position = self.positions[symbol]
            vqty, vwp = position.qty, position.price

        #longs
        if vqty > 0:
            # BUYS
            if fill.side == Order.BUY:
                # add long
                vwp = (vqty * vwp) + (fill.price * fill.qty)
                vqty += fill.qty
                vwp = vwp/float(vqty)
                self.profit_loss(None,fill,vqty)     #mark new position
            else:
            # SELLS
                if vqty >= fill.qty:
                    # reduce long
                    vqty -= fill.qty
                    self.profit_loss(fill.qty * (fill.price - vwp),fill,vqty)
                else:
                    # become net short
                    net_qty = vqty - fill.qty
                    self.profit_loss(vqty * (fill.price - vwp),fill,net_qty)
                    vqty = net_qty
                    vwp = fill.price
        #shorts
        elif vqty < 0:
            if fill.side == Order.SELL:
                # add short
                vwp = (-vqty * vwp) + (fill.price * fill.qty)
                vqty -= fill.qty
                vwp = -vwp/float(vqty)
                self.profit_loss(None,fill,vqty)     #mark new position
            else:
                # reduce short
                if abs(vqty) >= fill.qty:
                    vqty += fill.qty
                    self.profit_loss(fill.qty * (vwp - fill.price),fill,vqty)
                else:
                    # become net long
                    net_qty = vqty + fill.qty
                    self.profit_loss(abs(vqty) * (vwp - fill.price),fill,net_qty)
                    vqty = net_qty
                    vwp = fill.price
        #flat
        elif vqty == 0:
            vqty = fill.qty
            if fill.side == Order.SELL: vqty = -fill.qty
            vwp = fill.price
            self.profit_loss(None,fill,vqty)     #mark new position

        # handle flattened positions
        if vqty == 0: vwp =0

        self.positions[symbol] = Position(symbol,vqty,vwp)
        self.log.info("updated posn: %s" % self.positions[symbol])


    def profit_loss(self,pnl,fill,net_qty):

        fq = fill.qty if fill.side == Order.BUY else -fill.qty
        trade = collections.OrderedDict([ 
            ('symbol', fill.symbol),
            ('qty', fq),
            ('price',fill.price),
            ('pnl',pnl),
            ('net_qty',net_qty),
            ('timestamp',fill.timestamp)
        ])
        self.trading_activity[fill.symbol].append(trade)
        self.log.info("trade: %s" % dict(trade))


    ##exit cleanup
    def cleanup(self):
        for symbol, position in self.positions.iteritems():
            qty = position.qty
            if qty == 0: continue
            side = Order.SELL
            if qty < 0: side = Order.BUY

            ## send closing orders
            self.send_order(Order(self.name,symbol,side,qty,Order.MARKET,None,None))


    ## kills the thread
    def shutdown(self):
        self.log.info('Strategy Thread Stopped.')
        self.running = False



    def run(self):

        while self.running:

            ##sent back from portfolio
            ##IN_fills.get() returns a list: [fill0], or [fill1, fill2, ...]

            # FIX NOT NEEDED ? 
            # orders = []
            with self.lock:
                try:
                    fill = self.IN_fills.peek()
                    if fill.timestamp <= self.current_timestamp:
                        fill = self.IN_fills.get()
                        self.update_positions(fill)
                        self.update_orders(fill)
                except IndexError:
                    pass

                ### send out new orders to the portfolio
                for order in self.orders:
                    self.log.info("sending: %s" % order)
                    self.OUT_orders.put(copy.deepcopy(order))
                    # FIX NOT NEEDED ? 
                    ##orders.append(order)
                if self.orders:
                    del self.orders[:]

            ## report the new fills and orders
            ## to the portfolio
            ##for item in itertools.chain(fills,orders):
            ##    self.OUT_portfolio.put(item)


    def pull(self, interval=0):

        if self.start_up:
            if self.IN_data:
                head = self.IN_data.peek()
                self.target_timestamp = head.timestamp + timedelta(seconds=interval)
                self.log.info("bar interval = %s seconds" % interval)
                self.log.info("next target_timestamp: %s" % self.target_timestamp)
                self.start_up = False

        ## TODO 
        ## what happens when price timestamp crosses multiple bar intervals? !!!

        price_book = None
        if self.IN_data:
            ## price_data = self.IN_data.peek()
            price_data = self.IN_data.get()

            self.log.info("price_book update: %s" % price_data)

            if interval == 0:
                price_book = PriceBook()
                price_book.update(price_data)

            else:

                if price_data.timestamp >= self.target_timestamp:

                    ## carry last price forward if current price ts > target_timestamp
                    if price_data.timestamp > self.target_timestamp:
                        self.log.info("filling last price forward to %s" % self.target_timestamp)
                        self.price_book.fill_forward(price_data,self.target_timestamp)
                    else:
                        self.price_book.update(price_data)

                    price_book = copy.deepcopy(self.price_book)
                    self.log.info("bundled: %s to %s" % (price_book.start_timestamp,price_book.last_timestamp))

                    self.target_timestamp = self.target_timestamp + timedelta(seconds=interval)
                    self.log.info("next target_timestamp: %s" % self.target_timestamp)
                    self.price_book.clear()

                self.price_book.update(price_data)

        return price_book



    ## flush out last bit of cached PriceDataBar info
    ## and do processing
    def flush(self):

        with self.lock:

            price_book = copy.deepcopy(self.price_book)
            self.target_timestamp = price_book.last_timestamp + timedelta(seconds=self.bar_interval)
            self.log.info("flushed bundle: %s to %s" % (price_book.start_timestamp,price_book.last_timestamp))
            self.log.info("next target_timestamp: %s" % self.target_timestamp)
            self.price_book.clear()

            if not price_book.empty():
                self.current_data = copy.deepcopy(price_book)
                self.current_timestamp = price_book.last_timestamp
                self.execute_on(price_book)


    def on_data(self,price_data):

        with self.lock:

            self.IN_data.put(price_data)
            self.log.debug('LIVE_DATA: %s'  % price_data)

            self.current_timestamp = price_data.timestamp

            ## deplete fill queue before acting on current data
            report_collect = False
            while self.IN_fills:
                if not report_collect:
                    self.log.info('collecting fills before execute_on() call')
                    report_collect = True

                fill = self.IN_fills.peek()
                if fill.timestamp <= self.current_timestamp:
                    fill = self.IN_fills.get()
                    self.update_positions(fill)
                    self.update_orders(fill)
                else:
                    ## no fills ready to be processed
                    break

            new_data = self.pull(interval=self.bar_interval)
            if new_data:
                self.log.debug('LIVE_BOOK: %s'  % new_data)
                self.current_data = copy.deepcopy(new_data)
                self.execute_on(new_data)

            self.latch.notify()


    ### used in simulations
    def on_data_sim(self,price_data):

        self.IN_data.put(price_data)
        self.log.debug('SIM_DATA: %s'  % price_data)

        self.current_timestamp = price_data.timestamp

        ## deplete fill queue before acting on current data
        report_collect = False
        while self.IN_fills:
            if not report_collect:
                self.log.info('collecting fills before execute_on() call')
                report_collect = True

            fill = self.IN_fills.peek()
            if fill.timestamp <= self.current_timestamp:
                fill = self.IN_fills.get()
                self.update_positions(fill)
                self.update_orders(fill)
            else:
                ## no fills ready to be processed
                break

        new_data = self.pull(interval=self.bar_interval)
        if new_data:
            self.log.debug('SIM_BOOK: %s'  % new_data)
            self.current_data = copy.deepcopy(new_data)
            self.execute_on(new_data)

        ### send out new orders to the EXCHANGE 
        for order in self.orders:
            self.log.info("sending: %s" % order)
            self.OUT_orders.put(copy.deepcopy(order))
        if self.orders:
            del self.orders[:]

        self.latch.notify()



    def on_EOD(self):
        self.log.info('EOD reset %s' % self.name)

        with self.lock:
            ## 1. clear orders
            self.OUT_orders.clear()
            ## 2. process remaining fills and MTM
            while self.IN_fills:
                fill = self.IN_fills.peek()
                if fill.timestamp <= self.current_timestamp:
                    fill = self.IN_fills.get()
                    self.log.info('grab EOD fill %s' % fill)
                    self.update_positions(fill)
                    self.update_orders(fill)
                else:
                    ## no fills ready to be processed
                    break
            ## make sure fill queue is cleared
            self.IN_fills.clear()

            ## reset the strategy
            self.reset()


    def __repr__(self):
        setup = "strategy_setup = %s" % pprint.pformat(self.strategy_setup)
        params = "strategy_params = %s" % pprint.pformat(self.strategy_params)
        return "\n".join([setup,params])

    def __str__(self):
        setup = "strategy_setup = %s" % pprint.pformat(self.strategy_setup)
        params = "strategy_params = %s" % pprint.pformat(self.strategy_params)
        return "\n".join([setup,params])


    ## override this to implement strategy       
    def execute_on(self,price_book):
        raise NotImplementedError

    ## override this to reset strategy       
    def reset(self):
        raise NotImplementedError






