
from MarketObjects import PriceData, parse_float, parse_date
from MarketObjects import parse_date_time
import os
import logging


class DataFeed(object):

    SENTINEL = object()

    def __init__(self,filename,use_header=None):
        self.filename = filename
        self.file_buffer = open(filename,'r')
        self.header = None
        self.use_header = use_header
        if self.use_header:
            self.header = self.use_header
        else:
            header = self.file_buffer.readline()
            header = header[:-1]
            self.header = header.split(',')
        self.header = [x.strip().lower() for x in self.header]
        self.count =0 

        self.log = logging.getLogger(__name__)
        self.log.info('Data Source = %s',filename)

        self.EOF = False

    def __iter__(self):
        return self

    def reset(self):
        self.EOF = False
        self.file_buffer.close()
        self.file_buffer = open(self.filename,'r')
        self.log.info('Reset Data Source = %s',self.filename)
        if not self.use_header:
            self.file_buffer.readline()
            ## pull off the header line
            ## self.header HAS ALREADY BEEN SET

    def next(self):
        if not self.EOF:
            line = self.file_buffer.readline()
            if line:
                line =line[:-1]
                self.log.debug("processing: %s" % line)
                line = line.split(',')
                line = [ x.strip() for x in line]
                data = dict(zip(self.header,line))
                self.count +=1
                return self.convert(data)
            else:
                self.EOF = True
                return DataFeed.SENTINEL
        else:
            raise StopIteration()

    def close(self):
        self.file_buffer.close()

    def convert(self,line):
        raise NotImplementedError



## Date,Open,High,Low,Close,Volume,Adj Close (yahoo daily feed) , Symbol tacked on
#2010-01-04,213.43,214.5,212.38,214.01,123432400,29.08,AAPL
class DataFeedDaily(DataFeed):
    def __init__(self,filename):
        DataFeed.__init__(self,filename)

    def convert(self,line):
        m = PriceData()
        m.symbol = line['symbol']
        m.timestamp = parse_date(line['date'])
        m.open = parse_float(line['open'])
        m.high = parse_float(line['high'])
        m.low = parse_float(line['low'])
        m.close = parse_float(line['close'])
        m.trade_volume = parse_float(line['volume'])
        return m

## Quant Quote 1m data bars 
## Date,Time,Open,High,Low,Close,Volume,Splits,Earnings,Dividends
## 20100104,1330,213.43,214.5,212.38,214.01,123432400,29.08,1,0,0.13
## it is ASSUMED that each file hold one symbol only - we will use  the filename given as the symbol name
class DataFeed_QuantQuote1m(DataFeed):
    def __init__(self,filename):
        ## Quant Quote files have no header:
        header = ['date','time','open','high','low','close','volume','splits','earnings','dividends']
        DataFeed.__init__(self,filename,use_header=header)
        self.filename = os.path.basename(filename)
        self.symbol = self.filename.split('.')[0]  ## take the non-CSV part as the symbol name

    def convert(self,line):
        m = PriceData()
        m.symbol = self.symbol 
        m.timestamp = parse_date_time(line['date'], line['time'])
        m.open = parse_float(line['open'])
        m.high = parse_float(line['high'])
        m.low = parse_float(line['low'])
        m.close = parse_float(line['close'])
        m.trade_volume = parse_float(line['volume'])
        return m


##     date,      time,       bid,       ask,    bidvol,    askvol   symbol
##  20100315,  08:30:00,  115.2500,  115.2700,     15400,      4600  SPY
class DataFeedIntraday(DataFeed):
    def __init__(self,filename):
        DataFeed.__init__(self,filename)

    def convert(self,line):
        m = PriceData()
        m.symbol = line['symbol']
        m.timestamp = parse_date_time(line['date'], line['time'])
        m.bid = parse_float(line['bid'])
        m.ask = parse_float(line['ask'])
        m.bid_volume = parse_float(line['bidvol'])
        m.ask_volume = parse_float(line['askvol'])
        return m

##     date,      time,       open, high, low, close, volume, symbol 
##  20100315,  08:30:00,  115.2500,  115.2700,     15400,      4600  SPY
class DataFeedBars(DataFeed):
    def __init__(self,filename):
        DataFeed.__init__(self,filename)

    def convert(self,line):
        m = PriceData()
        m.symbol = line['symbol']
        m.timestamp = parse_date_time(line['date'], line['time'])
        m.open = parse_float(line['open'])
        m.high = parse_float(line['high'])
        m.low = parse_float(line['low'])
        m.close = parse_float(line['close'])
        m.trade_volume = parse_float(line['volume'])
        return m

## take a list of data files and provides data 
## as a continuous data stream - data is fed in the order of the list
## data_type indicates which type of DataFeed object is created 
## for each file in the list

class DataFeedList(object):

    DATA_CLASS_LIBRARY = dict(  D=DataFeedDaily,
                                I=DataFeedIntraday,
                                B=DataFeedBars,
                                Q1m=DataFeed_QuantQuote1m)

    def __init__(self,filename_list,data_type):
        self.data_class = DataFeedList.DATA_CLASS_LIBRARY[data_type]
        self.master_list = filename_list[::-1]
        self.filename_list = self.master_list[:] 
        self.data_feed = None

        self.file_number = 0

        self.log = logging.getLogger(__name__)

    def reset(self):
        self.filename_list = self.master_list[:]
        
    def __iter__(self):
        return self

    def next(self):
        if not self.data_feed or self.data_feed.EOF:
            while self.filename_list: 
                next_file = self.filename_list.pop()
                self.file_number += 1
                self.log.debug("data file = %s, file_number = %d" % (next_file, self.file_number))
                try:
                    self.data_feed = self.data_class(next_file)
                    return self.data_feed.next()
                except Exception as e:
                    self.data_feed = None
                    self.log.critical('cannot create DataFeed for file: %s' % next_file)
                    self.log.critical(e)
            else:
                raise StopIteration
        else:
            return self.data_feed.next()












