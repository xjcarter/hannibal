
from datetime import datetime
import re
import collections
import Indicators
import copy

INTEGER = re.compile(r"^-?\d+$")
FLOAT = re.compile(r"^-?((\d*\.\d+)|(\d+\.\d*)|(\d+))$")
FLOAT_PARENTHESES = re.compile(r"^\(((\d*\.\d+)|(\d+\.\d*)|(\d+))\)$")
FLOAT_ENGINEERING = re.compile(r"^(-?\d(.\d+)?)|(-?\d?.\d+)[eE][+-]?\d+$")


def parse_date(date_string):

    if not date_string:
        return None

    if INTEGER.match(date_string):
        try:
            return datetime.strptime(date_string, '%Y%m%d')
        except ValueError:
            pass

    # not supported: '%m/%d/%Y'
    for match in ('%Y-%m-%d',
        '%Y %m %d',
        '%Y%m%d',
        '%Y-%d-%m',
        '%d-%b-%Y',
        '%d-%b-%y',
        '%b-%d-%Y',
        '%b-%d-%y',
        '%d %B %Y',
        '%d %b %Y',
        '%d %b %y',
        '%b %d %Y',
        '%b %d, %Y',
        '%b %d, %y',
        '%B %d, %Y',
        '%m/%d/%Y',
        '%m-%d-%Y',
        '%a %b %d %H:%M:%S %Z %Y',
        '%d%b%Y'):

        try:
            return datetime.strptime(date_string, match)
        except ValueError:
            pass

    return None

def parse_float(float_string, default_return=None):

    if isinstance(float_string, float):
        return float_string

    if not float_string:
        return default_return

    # Commas just cause trouble, so do '+' values, ignore them from the front of the string
    float_string = float_string.replace(',', '').lstrip('+').strip()

    if float_string == '-':
        return 0.0
    if FLOAT.match(float_string) or FLOAT_ENGINEERING.match(float_string):
        return float(float_string)
    if FLOAT_PARENTHESES.match(float_string):
        return float(float_string.strip('()')) * -1

    raise ValueError("Expected floating point received: %s" % float_string)
    return default_return

TimeTuple = collections.namedtuple('TimeTuple','hour minutes seconds millis')

def parse_time(time_str):
    import re
    if re.search(":",time_str):
        ## assuming time format H:M:S.millis
        ts = time_str.split('.')
        millis = 0
        if len(ts) > 1: millis = int(ts[1])
        base = ts[0].split(':')
        time_array = [int(x) for x in base]
        seconds = 0
        if len(base) > 2: seconds = time_array[2]
        return TimeTuple(hour=time_array[0], minutes=time_array[1], seconds=seconds, millis=millis)
    else:
        ## assuming int representation in military time, ie. 1330 = 1:30
        v = int(time_str)
        hour = v/100
        minutes = v % 100
        return TimeTuple(hour=hour, minutes=minutes, seconds=0, millis=0)


def parse_date_time(date_str, time_str):
    date = parse_date(date_str)
    time_t = parse_time(time_str)
    return datetime(date.year,date.month,date.day,time_t.hour,time_t.minutes,time_t.seconds,time_t.millis)


class Position(object):
    def __init__(self,symbol,qty,price):
        self.symbol = symbol
        self.qty = qty
        self.price = price

    def __repr__(self):
        return str(self.__dict__)


class PriceData(object):

    def __init__(self):
        self.timestamp = None
        self.symbol = None
        self.bid = None
        self.ask = None
        self.bid_volume = None
        self.ask_volume = None
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.trade_volume = None

    def __repr__(self):
        return str(self.__dict__)

class PriceDataBar(PriceData):

    def __init__(self):
        super(PriceDataBar, self).__init__()
        self.start_timestamp = None

    def _pricemax(self,a,b):
        if a == None:
            return b
        elif b == None:
            return a
        else:
            return max(a,b)

    def _pricemin(self,a,b):
        if a == None:
            return b
        elif b == None:
            return a
        else:
            return min(a,b)

    def update(self, market_data):
        m = market_data

        if not self.start_timestamp:
            self.start_timestamp = m.timestamp

        price = m.close
        sz = m.trade_volume

        ## bid/ask data takes precedent over 'closing' data
        ## singular trade price/amount quotes are
        ## captured in the close and trade_volume fields

        if m.bid and m.ask:
            price = 0.5 * (m.ask + m.bid)
            sz = 0.5 * (m.ask_volume + m.bid_volume)

        self.timestamp = m.timestamp
        self.symbol = m.symbol
        self.bid = m.bid
        self.ask = m.ask
        self.bid_volume = m.bid_volume
        self.ask_volume = m.ask_volume

        if not self.open: self.open = price
        hi = lo = price
        if m.bid and m.ask:
            hi = m.ask
            lo = m.bid
        self.high = self._pricemax(self.high,hi)
        self.low = self._pricemin(self.low,lo)
        self.close = price
        if not self.trade_volume:
            self.trade_volume = sz
        else:
            self.trade_volume += sz

    def postOHLC(self,market_data):
        m = market_data

        self.start_timestamp = None
        self.open = m.open
        self.high = m.high
        self.low = m.low
        self.close = m.close
        self.trade_volume = m.trade_volume
        self.timestamp = m.timestamp

        self.ask = self.bid = None
        self.ask_volume = self.bid_volume = None


    def clear(self):
        for k in self.__dict__:
            self.__dict__[k] = None

    def __repr__(self):
        return str(self.__dict__)



class PriceBook(object):
    ## holds composite market data by symbol
    ## over the updating time interval

    def __init__(self):
        self.data = {}
        self.start_timestamp = None
        self.last_timestamp = None

    def update(self, market_data):
        p = None
        sym = market_data.symbol
        try:
            p = self.data[sym]
        except KeyError:
            self.data[sym] = PriceDataBar()
            p = self.data[sym]

        p.update(market_data)
        if not self.start_timestamp:
            self.start_timestamp = market_data.timestamp 
        if not self.last_timestamp:
            self.last_timestamp = market_data.timestamp 
        if market_data.timestamp > self.last_timestamp:
            self.last_timestamp = market_data.timestamp

    def __getitem__(self,key):
        return self.data[key]

    def keys(self):
        return self.data.keys()

    def empty(self):
        return len(self.data.keys()) == 0

    ## update the price_book to have timestamp = override value
    def fill_forward(self,market_data,ts_override):
        sym = market_data.symbol
        p = None
        try:
            p = self.data[sym]
        except KeyError:
            self.data[sym] = PriceDataBar()
            p = self.data[sym]
            override_data = copy.deepcopy(market_data)
            override_data.timestamp = ts_override    
            p.update(override_data)

        if not self.start_timestamp:
            self.start_timestamp = ts_override 
        if not self.last_timestamp:
            self.last_timestamp = ts_override 
        if ts_override > self.last_timestamp:
            self.last_timestamp = ts_override 


    def clear(self):
        self.data = {}
        self.start_timestamp = None
        self.last_timestamp = None

    def __repr__(self):
        s = []
        for sym, data in self.data.iteritems():
            s.append("%s" % data)
        p = "\n".join(s)
        p += "start: %s\n" % self.start_timestamp
        p += "last: %s" % self.last_timestamp
        return p




class Fill(object):

    __id = 0
    @classmethod
    def generate_id(cls):
        Fill.__id += 1
        return Fill.__id

    def __init__(self, symbol, price, qty, side, timestamp, order_id, qty_left=None):
        self.qty = qty
        self.price = price
        self.symbol = symbol
        self.side = side
        ## optional used in reporting partial fill
        self.qty_left = qty_left
        self.order_id = order_id
        self.fill_id = Fill.generate_id()
        self.timestamp = timestamp

        ## optional info identifier that can be used to tag a fill
        self.tag = None

    def __repr__(self):
        return str(self.__dict__)


class Order(object):

    __id = 0
    @classmethod
    def generate_id(cls):
        Order.__id += 1
        return Order.__id

    ## order types
    MARKET = 'MKT' 
    LIMIT = 'LMT' 
    STOP_LIMIT = 'STPLMT' 
    STOP = 'STP'
    MOC = 'MOC'
    MOO = 'MOO'

    ## order side
    BUY = 'BUY' 
    SELL = 'SELL'

    def __init__(self, owner, symbol, side, qty, order_type, limit_price, stop_price=None):
        self.order_id = '%s_%d' % (owner,Order.generate_id())
        self.owner = owner
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.qty_left = qty
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.timestamp = None

    def stamp_time(self,timestamp):
        self.timestamp = timestamp

    def signed_qty(self):
        q = self.qty
        if self.side == Order.SELL:
            q = -self.qty
        return q

    def __repr__(self):
        return str(self.__dict__)



## holds indicators for a given symbol
class IndicatorMap(object):
    def __init__(self,indicator_defs):
        ## create an array of indicator definitions

        ## Indicator map takes a list of indicator definitions:
        ## list of dicts(local_name, class_name, kwargs for class_name(**kwargs) constructor)
        self.definitions = indicator_defs

        ## dict (key= symbol, value= dict(key= name, value= Indicators))
        self.idict = {}
        self.overrides = {} 

    ## override generic indicator setup
    ## with custom setting specfic to a symbol
    ## list = [ (symbol,name,{kwargs}) ]
    def override(self,override_list):
        self.overrides = dict([((x[0],x[1]),x[2]) for x in override_list])

    ## reset all indicators = start by building a completely new map
    def reset(self):
        self.idict = {}

    ## dynamically build indicators as requested for a symbol
    def __getitem__(self,symbol):
        try:
            indicators = self.idict[symbol]
        except KeyError:
            self.idict[symbol] = {}
            indicators = self.idict[symbol]

            ## build out all the indictors based on the definitions given
            for indicator_def in self.definitions:
                name = indicator_def['name']
                class_name = indicator_def['class_name']
                kwargs = self.overrides.get((symbol,name),indicator_def['kwargs'])

                ## dynamically build an indicator of 'class_name'
                ## defined within the 'Indicators.py' module
                indicators[name] = getattr(Indicators,class_name)(**kwargs)

        return indicators




