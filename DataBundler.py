
from datetime import timedelta
from MarketObjects import PriceBook
from DataQueues import DQueue
from DataFeed import DataFeedIntraday, DataFeed 
import sys

class NullWriter(object):
    def __init__(self):
        pass
    def __enter__(self):
        pass
    def __exit__(self):
        pass

    def close(self):
        pass

    def write(self,s):
        print s[:-1]


class DataBundler(object):

    def __init__(self, bar_interval, filename=None):


        self.writer = NullWriter()
        if filename:
            self.writer = open(filename,"w") 

        self.target_timestamp = None

        self.price_book = PriceBook()  # market data bucket
        self.bar_interval = bar_interval ## seconds 

        self.start_up = True
        self.IN_data = DQueue()


    def _bundle(self):

        if self.start_up:
            if self.IN_data:
                head = self.IN_data.peek()
                self.target_timestamp = head.timestamp + timedelta(seconds=self.bar_interval)
                self.writer.write("date, time, open, high, low, close, volume, symbol\n")
                self.start_up = False

        if len(self.IN_data) > 0:
            price_data = self.IN_data.peek()
            if price_data.timestamp > self.target_timestamp:
                if not self.price_book.empty():
                    self.print_book(self.price_book)
                    self.target_timestamp += timedelta(seconds=self.bar_interval)
                    self.price_book.clear()
            
            price_data = self.IN_data.get()
            self.price_book.update(price_data)

    def print_book(self,price_book):

        def split(ts):
            date = "%d-%02d-%02d" % (ts.year,ts.month,ts.day)
            clocktime = "%02d:%02d:%02d" % (ts.hour,ts.minute,ts.second)
            return [date,clocktime]

        for sym, data in price_book.data.iteritems():
            s = []
            s.extend(split(data.timestamp))
            s.extend([data.open, data.high, data.low, data.close])
            s.extend([data.trade_volume,data.symbol])
            bar = ", ".join([str(x) for x in s])
            bar = bar + '\n'
            self.writer.write(bar)

    def close(self):
        self.writer.close()

    def bundle_data(self,price_data):

        self.IN_data.put(price_data)
        self._bundle()


if __name__ == '__main__':
    _, infile, outfile, length = sys.argv

    bundler = DataBundler(bar_interval=int(length),filename=outfile)
    simData = DataFeedIntraday(infile)
    for market_data in simData:
        if market_data != DataFeed.SENTINEL:
            bundler.bundle_data(market_data)
    bundler.close()


