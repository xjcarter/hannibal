
from DataQueues import DQueue, DataLatch
from Exchange import Exchange
from Portfolio import Portfolio
from DataFeed import DataFeedDaily, DataFeedIntraday, DataFeedBars
from MarketObjects import Order, Fill, parse_date
from MStrategy import MStrategy
from pprint import pprint
import logging
import datetime
import threading
import time

# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='test.log',
                    filemode='w')

log = logging.getLogger('Test')

class Tester(threading.Thread):
    def __init__(self):
        super(Tester,self).__init__()
        self.running = True
        self.IN_queue = None

    def shutdown(self):
        self.running = False

    def run(self):

        while self.running:

            try:
                fill = self.IN_queue.get()
                log.info("fill= %s",fill)
            except IndexError:
                pass

      

def test_exchange():

    latch = DataLatch(1)

    ## exchange queues
    order_q = DQueue()
    fill_q = DQueue()

    exchange = Exchange()
    exchange.latch = latch

    ## bind exchange and portfolio together
    tester = Tester()
    exchange.IN_orders = order_q
    exchange.OUT_fills = fill_q
    tester.IN_queue = fill_q

    exchange.start()
    tester.start()
    o1 = Order('test','AAPL',Order.BUY,100,Order.MARKET,None,None)
    o1.stamp_time(parse_date("20140311"))
    order_q.put(o1)
    o2 = Order('test','AAPL',Order.BUY,200,Order.MARKET,None,None)
    o2.stamp_time(parse_date("20140816"))
    order_q.put(o2)
    o3 = Order('test','AAPL',Order.SELL,300,Order.MARKET,None,None)
    o3.stamp_time(parse_date("20140101"))
    order_q.put(o3)


    simData = DataFeedDaily('AAPL.csv')
    for market_data in simData:
        latch.trap(market_data)
        exchange.on_data(market_data)

    exchange.shutdown()
    tester.shutdown()
    exchange.join()
    tester.join()

def test_strategy_fills(side):
    ## handle long and short fills, all possiblities
    ## strategy queues
    

    latch = DataLatch(1)

    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strategy = MStrategy('test_strategy',strategy_params={'length':10})

    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    strategy.start()

    ts = datetime.datetime(2014,8,16,12,30,0)

    ## build inital position
    s1_fill_q.put(Fill('AAPL',100.00,100,side,ts,1))
    s1_fill_q.put(Fill('AAPL',101.50,50,side,ts,2))
    s1_fill_q.put(Fill('AAPL',110.00,50,side,ts + datetime.timedelta(seconds=10),3))

    rev = Order.SELL
    if side == rev: rev = Order.BUY
    ## take some of off
    s1_fill_q.put(Fill('AAPL',107.00,20,rev,ts + datetime.timedelta(seconds=20),4))
    s1_fill_q.put(Fill('AAPL',107.00,20,rev,ts + datetime.timedelta(seconds=25),5))

    ## flip position
    s1_fill_q.put(Fill('AAPL',110.00,200,rev,ts + datetime.timedelta(seconds=100),6))
    s1_fill_q.put(Fill('AAPL',108.50,10,rev,ts + datetime.timedelta(seconds=110),7))
    s1_fill_q.put(Fill('AAPL',106.50,100,rev,ts + datetime.timedelta(seconds=110),8))

    ##close position
    s1_fill_q.put(Fill('AAPL',109.00,100,side,ts + datetime.timedelta(seconds=200),9))
    s1_fill_q.put(Fill('AAPL',109.00,50,side,ts + datetime.timedelta(seconds=200),10))

    time.sleep(5)

    strategy.shutdown()
    strategy.join()




def test_strategy_order_update():
    ## do partial fill and update, both sides

    latch = DataLatch(1)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    ts = datetime.datetime(2014,8,16,12,30,0)

    strategy = MStrategy('test_strategy',strategy_params={'length':10})
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    strategy.start()

    o1 = Order(strategy.name,'AAPL',Order.SELL,100,Order.MARKET,None,None)
    o2 = Order(strategy.name,'AAPL',Order.SELL,200,Order.MARKET,None,None)

    p1 = Order(strategy.name,'AAPL',Order.BUY,100,Order.MARKET,None,None)
    p2 = Order(strategy.name,'AAPL',Order.BUY,200,Order.MARKET,None,None)

    strategy.send_order(o1)
    strategy.send_order(o2)
    strategy.send_order(p1)
    strategy.send_order(p2)

    # allow time for orders to be sent
    time.sleep(2)

    s1_fill_q.put(Fill('AAPL',100.00,100,Order.SELL,ts,o1.order_id))
    s1_fill_q.put(Fill('AAPL',101.50,50,Order.SELL,ts,o2.order_id, qty_left=150))

    s1_fill_q.put(Fill('AAPL',104.00,100,Order.BUY,ts,p1.order_id))
    s1_fill_q.put(Fill('AAPL',105.50,70,Order.BUY,ts,p2.order_id,qty_left=130))

    time.sleep(2)

    strategy.shutdown()
    strategy.join()


def test_strategy_execute():

    latch = DataLatch(2)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strategy = MStrategy('test_strategy',strategy_params={'length':10})
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    exchange = Exchange()
    exchange.IN_orders = strategy.OUT_orders
    exchange.OUT_fills = strategy.IN_fills
    exchange.latch = latch

    exchange.start()
    strategy.start()

    log.info("START JOB= %s" % datetime.datetime.now())

    simData = DataFeedIntraday('20100315.SPY.csv')
    for market_data in simData:
        latch.trap(market_data)
        exchange.on_data(market_data)
        strategy.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    strategy.shutdown()
    exchange.join()
    strategy.join()

    log.info("END JOB= %s" % datetime.datetime.now())
    log.info("LEN DATA JOB= %s" % simData.count)


def test_portfolio():

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strategy = MStrategy('test_strategy',strategy_params={'length':10})
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    portfolio = Portfolio('test_porto',None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    log.info("START JOB= %s" % datetime.datetime.now())

    simData = DataFeedIntraday('20100315.SPY.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    log.info("STAT JOB= %s" % datetime.datetime.now())

    # portfolio.stats(write_data=True)

    log.info("END JOB= %s" % datetime.datetime.now())
    log.info("LEN DATA JOB= %s" % simData.count)


def test_multiple_symbols():

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strategy = MStrategy('test_strategy',strategy_params={'length':10})
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    portfolio = Portfolio('test_porto',None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    log.info("START JOB= %s" % datetime.datetime.now())

    ## combined file of SPY, IWM, and QQQQ
    simData = DataFeedIntraday('20100315.XXX.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    log.info("STAT JOB= %s" % datetime.datetime.now())

    port_stats = portfolio.stats(filename='TESTER.xls')
    pprint(port_stats)

    log.info("END JOB= %s" % datetime.datetime.now())
    log.info("LEN DATA JOB= %s" % simData.count)


def test_multiple_strategies():

    latch = DataLatch(4)
    s1_order_q = DQueue()
    s2_order_q = DQueue()
    s1_fill_q = DQueue()
    s2_fill_q = DQueue()

    strategy = MStrategy('test_strategy',strategy_params={'length':10})
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    strategy2 = MStrategy('test_strategy2',strategy_params={'length':5})
    strategy2.IN_fills = s2_fill_q
    strategy2.OUT_orders = s2_order_q
    strategy2.latch = latch

    portfolio = Portfolio('portfolio',None)
    portfolio.latch = latch
    portfolio.add(strategy)
    portfolio.add(strategy2)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()
    strategy2.start()

    log.info("START JOB= %s" % datetime.datetime.now())

    ## combined file of SPY, IWM, and QQQQ
    simData = DataFeedIntraday('20100315.XXX.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        strategy2.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    strategy2.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()
    strategy2.join()

    log.info("STAT JOB= %s" % datetime.datetime.now())

    portfolio.stats(filename='TESTER.xls')

    log.info("END JOB= %s" % datetime.datetime.now())
    log.info("LEN DATA JOB= %s" % simData.count)


def test_bars(length=50):

    latch = DataLatch(3)
    s1_order_q = DQueue()
    s1_fill_q = DQueue()

    strat_name = 'test_%d' % length
    strategy = MStrategy(strat_name,strategy_params={'length':length})
    strategy.bar_interval = 0
    strategy.IN_fills = s1_fill_q
    strategy.OUT_orders = s1_order_q
    strategy.latch = latch

    porto_name = 'portfolio_%d' % length
    portfolio = Portfolio(porto_name,None)
    portfolio.latch = latch
    portfolio.add(strategy)

    exchange = Exchange()
    exchange.IN_orders = portfolio.OUT_orders
    exchange.OUT_fills = portfolio.IN_fills
    exchange.latch = latch


    exchange.start()
    portfolio.start()
    strategy.start()

    log.info("START JOB %s = %s" % (porto_name,datetime.datetime.now()))

    simData = DataFeedBars('20100315.SPY.1m.csv')
    for market_data in simData:
        latch.trap(market_data)
        ## ORDER MATTERS! 
        ## this allows submit-fill loop to happen in a single on_data() event
        strategy.on_data(market_data)
        portfolio.on_data(market_data)
        exchange.on_data(market_data)

    ## do any final processing
    #strategy.flush()

    exchange.shutdown()
    portfolio.shutdown()
    strategy.shutdown()
    exchange.join()
    portfolio.join()
    strategy.join()

    # portfolio.stats(write_data=True)
    filename = 'TEST_BAR_X_%d.xls' % length
    port_stats = portfolio.stats(filename=filename)

    print 'portfolio stats'
    pprint(port_stats)

    log.info("END JOB %s = %s" % (porto_name,datetime.datetime.now()))

    return portfolio


def test_two():
    ##sim_latch = DataLatch(1)
    for sim_length in [30,50]:
        ## sim_latch.trap(sim_length)
        test_bars(sim_length)
        ##sim_latch.notify()


if __name__ == "__main__":

    #test_exchange()

    #test_strategy_fills(Order.BUY)
    #test_strategy_fills(Order.SELL)

    #test_strategy_order_update()
    
    #test_strategy_execute()

    #test_portfolio()

    #test_multiple_symbols()
    
    #test_multiple_strategies()
   
    #test_two()
    
    p = test_bars()
    p.save('test.pkl')
    































