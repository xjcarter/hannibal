
import sys
import math
from collections import deque

class MetricError(Exception):pass

def unpack(vectorlist,index):
    t = [x[index] for x in vectorlist]
    return t

def _average(s,length):
    tmp = list(s)
    t = len(tmp)
    assert(t >= length), "series length = %d, length param = %d" % (t,length)
    mean = sum(tmp[:length]) / (length * 1.0)
    return mean

def _expma(price, avg, coeff):
    newval =avg
    if avg is None:
        newval = price
    else:
        newval = price * coeff + ( 1 - coeff) * avg
    return newval

def _roc(s,length):
    tmp = list(s)
    t = len(tmp)
    assert(t >= length), "series length = %d, length param = %d" % (t,length)
    assert(length>0), "length param <= 0"
    assert(tmp[length-1]>0), "denom <= 0"
    v = (tmp[0] - tmp[length-1])/tmp[length-1]
    return v

def _median(s,length):
    tmp = list(s)
    tmp = tmp[:length]
    tmp.sort()
    n = int(length/2)
    return tmp[n]

def average(lst):
    sum = 0.0
    cnt = 0
    avg = None
    if len(lst) > 0:
        for x in lst:
            if x is not None:
                sum += x
                cnt += 1
    if cnt > 0: avg = sum/cnt
    return avg

def stdv(lst,avg):
    sum = 0.0
    std = None
    cnt = 0
    if len(lst) > 0:
        for x in lst:
            if x is not None:
                sum += (x - avg)*(x-avg)
                cnt += 1

    if cnt > 0: std = sum/cnt
    if std is not None: std = math.sqrt(std)
    return std

class RiskMgr:

    def __init__(self,ticksz,tickval,unitsz,cap,ff,maxunits):
        self.ticksz = ticksz
        self.tickval = tickval
        self.capital = cap
        self.fixedf = ff
        self.unitsz = unitsz
        self.allowZero = False
        self.dollarStop = None
        self.maxunits = maxunits
        self.fixedSz = None

    def setFixedSize(self,famt):
        self.fixedSz = famt

    def allowZeroAmount(self,flag):
        self.allowZero = flag

    def setDollarStop(self,dstop):
        self.dollarStop = dstop

    def addPNL(self,pnl):
        self.capital += pnl

    def allocate(self,stpAmount):
        if self.fixedSz is not None: return self.fixedSz

        sz = 0
        assert stpAmount > 0

        unit_risk = stpAmount/self.ticksz * self.tickval
        allc = max(0,self.fixedf * self.capital)
        if self.dollarStop is not None: allc = self.dollarStop

        sz = (int(allc/unit_risk) // self.unitsz) * self.unitsz
        #print "alloc= ", allc, "sz= ", sz
        if self.allowZero == False: sz = max(self.unitsz,sz)
        sz = min(self.maxunits,sz)
        return sz


class PriceBar:

    def __init__(self):
        self.first = self.last = None
        self.high = self.low = None
        self.age = 0
        self.time = None
        self.bidvol = 0
        self.askvol = 0
        self.totvol = 0
        self.vwap = 0
        self.psum = 0

    def collect(self, bid, ask=None, bidv=0, askv=0):
        if ask is None: ask = bid
        mid = (bid+ask)/2.0
        self.psum += mid

        midv = (bidv+askv)/2.0
        self.bidvol += bidv
        self.askvol += askv

        if midv > 0: self.vwap = ((self.vwap*self.totvol) + (mid * midv))/(self.totvol+midv)
        self.totvol += midv

        if self.first is None: self.first = mid
        self.last = mid

        if self.high is None or ask > self.high: self.high = ask
        if self.low is None or bid < self.low: self.low = bid
        self.age += 1

    def stamptime(self, timestr):
        self.time = timestr

    def getVWAP(self):
        r = None
        if self.vwap == 0 and self.age > 0:
            r = self.psum/self.age
        else:
            r = self.vwap
        return r

    def getAVP(self):
        r = None
        if self.age > 0: r = self.psum/self.age
        return r

    def clone(self):
        j = PriceBar()
        j.first = self.first
        j.last = self.last
        j.high = self.high
        j.low = self.low
        j.age = self.age
        j.time = self.time
        j.bidvol = self.bidvol
        j.askvol = self.askvol
        j.totvol = self.totvol
        j.vwap = self.vwap
        j.psum = self.psum

        return j

    def setvalues(self,opn,high,low,close):
        self.first = opn
        self.last = close
        self.high = high
        self.low = low
        self.age = 1

    def collect_bar(self,vector):
        for v in vector:
            self.collect(v)

    def vector(self):
        v = [self.first,self.high,self.low,self.last]
        return v

    def isEmpty(self):
        v = False
        if self.age <= 0: v = True
        return v

    def clear(self):
        self.first = None
        self.last = None
        self.high = None
        self.low = None
        self.age = 0
        self.time = None
        self.bidvol = 0
        self.askvol = 0
        self.totvol = 0
        self.vwap = 0
        self.psum = 0


    def __str__(self):
        s = "Empty"
        if self.first is not None:
             s = "%8.5f %8.5f %8.5f %8.5f" % (self.first, self.high, self.low, self.last)
             if self.time is not None:
                t = "%10s " % self.time
                s = t + s
        return s


class Metric:

    def __init__(self):
        self.series = deque()
        self.hlimit = 50

    def __getitem__(self,index):
        if self.series and index >= 0 and index < len(self.series):
            return self.series[index]
        return None

    def __nonzero__(self):
        return True

    def size(self):
        return len(self.series)

    def reset(self):
        self.series.clear()

    def push(self,price):
        pass

    def feed(self,series2):
        tmp = list(series2)
        tmp.reverse()
        for i in tmp: self.push(i)

    def sethistory(self,limit):
        assert limit > 1
        self.hlimit = limit

    def _pop(self):
        if len(self.series) > self.hlimit: self.series.pop()




class TimeSeries(Metric):
    def __init__(self,capacity=None):
        Metric.__init__(self)
        self.capacity = capacity

    def push(self, price):
        self.series.appendleft(price)
        if self.capacity is not None and len(self.series) > self.capacity:
            self.series.pop()

         
class VEL(Metric):

    def __init__(self,lex,s1,s2,minpts):
        Metric.__init__(self)
        self.coeff = 2.0/lex
        self.s1, self.s2 = (s1, s2)
        self.xma1 = self.xma2 = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0
        self.move = None

    def reset(self):
        Metric.reset(self)
        self.xma1 = self.xma2 = None
        self.minpts = minpts
        self.prices.clear()
        self.count = 0
        self.move = None

    def push(self, price):
        self.prices.appendleft(price)
        self.count += 1
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            a = math.fabs(c)
            self.move = _expma(c,self.move,self.coeff)
            self.prices.pop()

        if self.count >= self.minpts:
            y = self.move
            self.xma1 = _expma(y,self.xma1,self.s1)
            self.xma2 = _expma(self.xma1,self.xma2,self.s2)
            v = [self.xma1,self.xma2]
            self.series.appendleft(v)
            self._pop()

class DRV(Metric):

    def __init__(self,coeff,s1,s2,minpts):
        Metric.__init__(self)
        self.coeff = coeff
        self.s1, self.s2 = (s1, s2)
        self.xma1 = self.xma2 = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0
        self.move = self.mass = None

    def reset(self):
        Metric.reset(self)
        self.xma1 = self.xma2 = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0
        self.move = self.mass = None

    def push(self, price):
        self.prices.appendleft(price)
        self.count += 1
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            a = math.fabs(c)
            self.move = _expma(c,self.move,self.coeff)
            self.mass = _expma(a,self.mass,self.coeff)
            self.prices.pop()

        if self.count >= self.minpts:
            if self.mass > 0:
                drv = self.move/self.mass
                self.xma1 = _expma(drv,self.xma1,self.s1)
                self.xma2 = _expma(self.xma1,self.xma2,self.s2)
                v = [drv,self.xma1,self.xma2]
                self.series.appendleft(v)
                self._pop()


class KST(Metric):

    def __init__(self,lengths):
        Metric.__init__(self)
        ### lengths default = [6,12,18,24]
        self.lengths = lengths
        self.maxlen = max(lengths)
        self.prices = deque()
        self.kma = None
        self.xrocs = [None,None,None,None]

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.kma = None
        self.xrocs = [None,None,None,None]

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > self.maxlen:
            cfs = [0.285,0.285,0.285,0.20]
            kst = 0
            for i, r in enumerate(self.lengths):
                roc = _roc(self.prices,r)
                self.xrocs[i] = _expma(roc,self.xrocs[i], cfs[i])
                kst += self.xrocs[i] * (i+1)
            self.kma = _expma(kst,self.kma,0.20)
            vec = (kst,self.kma)
            self.series.appendleft(vec)
            self._pop()

class LR(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) >= self.length:
            ys = list(self.prices)
            ys = ys[:self.length]
            ys.reverse()
            n = self.length
            sumx = sumxy = sumx2 = sumy = 0
            for i in range(n):
                x = i+1
                sumx += x
                sumx2 += (x*x)
                sumy += ys[i]
                sumxy += ys[i] * x

            avgx = float(sumx)/n
            avgy = float(sumy)/n

            slope = (sumxy - n*(avgx*avgy))/(sumx2 - n*(avgx*avgx))
            intercept = avgy - slope*avgx
            ### angle = arctangent(slope) * 180/(22.0/7)

            self.series.appendleft((slope,intercept))
            self.prices.pop()
            self._pop()


class RSI(Metric):

    def __init__(self,length,coeff=None):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()
        self.chgs = deque()
        self.xma = None
        self.coeff = coeff
        self.cntpct = False

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.chgs.clear()

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def setCountPct(self,flag):
        self.cntpct = flag

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.chgs.appendleft(c)
            if len(self.chgs) >= self.length:
                u = d = 0
                ucnt = 0
                for c in self.chgs:
                    if c > 0:
                        u += c
                        ucnt += 1
                    if c < 0:
                        d -= c
                rsi = 0
                if (u+d) > 0: rsi = u/(u+d)
                if self.coeff is not None:
                    self.xma = _expma(rsi,self.xma,self.coeff)
                    self.series.appendleft([rsi,self.xma])
                else:
                    if self.cntpct == True:
                        rpct = ucnt/self.length
                        self.series.appendleft([rsi,rpct])
                    else:
                        self.series.appendleft(rsi)

                self.chgs.pop()
                self.prices.pop()
                self._pop()

### exponential RSI
### coeff=1.0 = regular rsi calc, otherwise coeff smoothes numerator and denominator exponetially before doing the division
### acoeff and bcoeff allow for longer smoothings
class RSX(Metric):

    def __init__(self,length,coeff=1.0,acoeff=None,bcoeff=None):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()
        self.chgs = deque()
        self.xchgs = None
        self.xups = None
        self.coeff = coeff
        self.acoeff = acoeff
        self.bcoeff = bcoeff
        self.xma = None
        self.xmb = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.chgs.clear()
        self.xma = None
        self.xmb = None

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.chgs.appendleft(c)
            if len(self.chgs) >= self.length:
                u = d = 0
                for c in self.chgs:
                    if c > 0:
                        u += c
                    if c < 0:
                        d -= c
                totchgs = u+d
                self.xups = _expma(u,self.xups,self.coeff)
                self.xchgs = _expma(totchgs,self.xchgs,self.coeff)
                rsx = 0
                if self.xchgs > 0: rsx = self.xups/self.xchgs
                if self.acoeff is not None:
                    self.xma = _expma(rsx,self.xma,self.acoeff)
                if self.bcoeff is not None:
                    self.xmb = _expma(rsx,self.xmb,self.bcoeff)
                self.series.appendleft([rsx,self.xma,self.xmb])
                self.chgs.pop()
                self.prices.pop()
                self._pop()

class STOCH_RSI(Metric):

    def __init__(self,rsi_length,width,len1,len2):
        Metric.__init__(self)
        self.width, self.len1, self.len2 = (width,len1,len2)
        self.rsi_length = rsi_length
        self.prices = deque()
        self.chgs = deque()
        self.rsv = deque()
        self.k = deque()
        self.d = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.chgs.clear()
        self.rsv.clear()
        self.k.clear()
        self.d.clear()

    def push(self, price):
        self.prices.appendleft(price)
        rsi_val = self.calc_rsi()
        if rsi_val: self.rsv.appendleft(rsi_val)
        if len(self.rsv) >= self.width:
            self.calc()
            self.rsv.pop()

    def calc_rsi(self):
        val = None
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.chgs.appendleft(c)
            if len(self.chgs) >= self.rsi_length:
                u = d = 0
                for c in self.chgs:
                    if c > 0:
                        u += c
                    if c < 0:
                        d -= c
                rsi = 0
                if (u+d) > 0: rsi = u/(u+d)
                val = rsi
                self.chgs.pop()
                self.prices.pop()

        return val

    def calc(self):
        width = self.width
        tmp = list(self.rsv)
        hi,lo = (max(tmp[:width]),min(tmp[:width]))
        r = hi - lo
        v= 0.5
        if r > 0: v = (tmp[0] - lo)/r
        self.k.appendleft(v)
        if len(self.k) >= self.len1:
            u = _average(self.k,self.len1)
            self.d.appendleft(u)
            if len(self.d) >= self.len2:
                w = _average(self.d,self.len2)
                ### v = %K, u = %D, w = slow %D
                vec = (v,u,w)
                self.series.appendleft(vec)
                self._pop()

class JSI(Metric):

    ### RSI with two smoothings

    def __init__(self,length,c1=0.33,c2=0.4):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()
        self.chgs = deque()
        self.rvs = deque()
        self.c1 = c1
        self.c2 = c2
        self.jsi = None
        self.jsi2 = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.chgs.clear()
        self.rvs.clear()
        self.jsi = None
        self.jsi2 = None

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.chgs.appendleft(c)
            if len(self.chgs) >= self.length:
                u = d = 0
                for c in self.chgs:
                    if c > 0:
                        u += c
                    if c < 0:
                        d -= c
                rsv = 0
                if (u+d) > 0: rsv = u/(u+d)
                self.jsi = _expma(rsv,self.jsi,self.c1)
                self.jsi2 = _expma(self.jsi,self.jsi2,self.c2)
                v = (rsv, self.jsi, self.jsi2)
                self.series.appendleft(v)
                self.chgs.pop()
                self.prices.pop()
                self._pop()

class ACC(Metric):

    def __init__(self,c1,minpts):
        Metric.__init__(self)
        self.c1 = c1
        self.minpts = minpts
        self.prices = deque()
        self.vels = deque()
        self.xma = self.velocity = self.accel = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.vels.clear()
        self.xma = self.velocity = self.accel = None
        self.count = 0

    def push(self, price):
        self.xma = _expma(price,self.xma,self.c1)
        self.prices.appendleft(self.xma)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.velocity = _expma(c,self.velocity,self.c1)
            self.vels.appendleft(self.velocity)
            if len(self.vels) > 1:
                vc = self.vels[0] - self.vels[1]
                self.accel = _expma(vc,self.accel,self.c1)
                self.count += 1
                if self.count >= self.minpts:
                    q = (self.velocity,self.accel)
                    self.series.appendleft(q)
                    self._pop()
                self.prices.pop()
                self.vels.pop()

class ACC2(Metric):

    def __init__(self,c1,c2,minpts):
        Metric.__init__(self)
        self.c1 = c1
        self.c2 = c2
        self.minpts = minpts
        self.prices = deque()
        self.vels = deque()
        self.xma = self.velocity = self.accel = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.vels.clear()
        self.xma = self.velocity = self.accel = None
        self.count = 0

    def push(self, price):
        self.xma = _expma(price,self.xma,self.c1)
        self.prices.appendleft(self.xma)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            self.velocity = _expma(c,self.velocity,self.c2)
            self.vels.appendleft(self.velocity)
            if len(self.vels) > 1:
                vc = self.vels[0] - self.vels[1]
                self.accel = _expma(vc,self.accel,self.c2)
                self.count += 1
                if self.count >= self.minpts:
                    q = (self.velocity,self.accel)
                    self.series.appendleft(q)
                    self._pop()
                self.prices.pop()
                self.vels.pop()

### xmo using smoothed price as proxy
class ZMO(Metric):

    def __init__(self,xc,length,c1,c2,minpts):
        Metric.__init__(self)
        self.xc, self.c1, self.c2 = (xc,c1,c2)
        self.length = length
        self.minpts = minpts
        self.prices = deque()
        self.xma = self.xma1 = self.xma2 = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.xma = self.xma1 = self.xma2 = None
        self.count = 0

    def push(self, price):
        self.xma = _expma(price,self.xma,self.xc)
        self.prices.appendleft(self.xma)
        if len(self.prices) >= self.length:
            self.count += 1
            self.calc()
            self.prices.pop()

    def calc(self):
        self.raw = self.prices[0] - self.prices[self.length-1]
        self.xma1 = _expma(self.raw,self.xma1,self.c1)
        self.xma2 = _expma(self.xma1,self.xma2,self.c2)
        if self.count >= self.minpts:
            self.series.appendleft([self.raw,self.xma1,self.xma2])
            self._pop()


class TSI(Metric):

    def __init__(self,c1,c2,minpts):
        Metric.__init__(self)
        self.c1, self.c2 = (c1,c2)
        self.minpts = minpts
        self.prices = deque()
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.count = 0

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            a = math.fabs(c)
            if a > 0:
                self.count += 1
                self.x1 = _expma(c,self.x1,self.c1)
                self.y1 = _expma(a,self.y1,self.c1)
                self.x2 = _expma(self.x1,self.x2,self.c2)
                self.y2 = _expma(self.y1,self.y2,self.c2)
                self.prices.pop()

            if self.count >= self.minpts:
                tsi = self.x2/self.y2
                self.series.appendleft(tsi)
                self._pop()

### SSI = serious strength index
### TSI and STX combined
class SSI(Metric):

    def __init__(self,c1,c2,minpts):
        Metric.__init__(self)
        self.c1, self.c2 = (c1,c2)
        self.minpts = minpts
        self.prices = deque()
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.count = 0

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, clos = self.prices[0]
            prev = self.prices[1][3]
            c = clos - prev
            top, bot = (max(hi,prev),min(lo,prev))
            wid = top - bot
            if wid > 0:
                self.count += 1
                self.x1 = _expma(c,self.x1,self.c1)
                self.y1 = _expma(wid,self.y1,self.c1)
                self.x2 = _expma(self.x1,self.x2,self.c2)
                self.y2 = _expma(self.y1,self.y2,self.c2)
                self.prices.pop()

        if self.count >= self.minpts:
           ssi = self.x2/self.y2
           self.series.appendleft(ssi)
           self._pop()


### TSI with sma/signal line
class TSI2(Metric):

    def __init__(self,c1,c2,malen,minpts):
        Metric.__init__(self)
        self.c1, self.c2 = (c1,c2)
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.malen = malen
        self.minpts = minpts
        self.prices = deque()
        self.raw = deque()
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.prices.clear()
        self.raw.clear()
        self.count = 0

    def push(self, price):
        self.prices.appendleft(price)
        self.count += 1
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            a = math.fabs(c)
            self.x1 = _expma(c,self.x1,self.c1)
            self.y1 = _expma(a,self.y1,self.c1)
            self.x2 = _expma(self.x1,self.x2,self.c2)
            self.y2 = _expma(self.y1,self.y2,self.c2)
            self.prices.pop()

            if self.count >= self.minpts:
                assert(self.y2 > 0)
                tsi = self.x2/self.y2
                self.raw.appendleft(tsi)
                if len(self.raw) >= self.malen:
                    a = _average(self.raw,self.malen)
                    self.series.appendleft([tsi,a])
                    self.raw.pop()
                    self._pop()

### TSI w/ xma signal line
class TSX(Metric):

    def __init__(self,c1,c2,xc,minpts):
        Metric.__init__(self)
        self.c1, self.c2 = (c1,c2)
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.xc = xc
        self.xma = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.x1 = self.x2 = self.y1 = self.y2 = None
        self.xma = None
        self.prices.clear()
        self.count = 0

    def push(self, price):
        self.prices.appendleft(price)
        self.count += 1
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            c = self.prices[0] - self.prices[1]
            a = math.fabs(c)
            self.x1 = _expma(c,self.x1,self.c1)
            self.y1 = _expma(a,self.y1,self.c1)
            self.x2 = _expma(self.x1,self.x2,self.c2)
            self.y2 = _expma(self.y1,self.y2,self.c2)
            self.prices.pop()

            if self.y2 > 0:
                tsi = self.x2/self.y2
                self.xma = _expma(tsi,self.xma,self.xc)
                if self.count >= self.minpts:
                    self.series.appendleft([tsi,self.xma])
                    self._pop()

### strength indicator
### Kaufman, pg 146
class STX(Metric):

    def __init__(self,c1,acoeff=None,bcoeff=None,minpts=5):
        Metric.__init__(self)
        self.c1 = c1
        self.x1 = self.y1 = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0
        self.xma = None
        self.xmb = None
        self.acoeff = acoeff
        self.bcoeff = bcoeff

    def reset(self):
        Metric.reset(self)
        self.x1 = self.y1 = None
        self.prices.clear()
        self.count = 0
        self.xma = None
        self.xmb = None

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        self.count += 1
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            prev = self.prices[1][3]
            c = close - prev
            top, bot = (max(hi,prev),min(lo,prev))
            wid = top - bot

            if wid > 0:
                self.x1 = _expma(c,self.x1,self.c1)
                self.y1 = _expma(wid,self.y1,self.c1)
                self.prices.pop()

                if self.count >= self.minpts:
                    stx = self.x1/self.y1
                    if self.acoeff is not None:
                        self.xma = _expma(stx,self.xma,self.acoeff)
                    if self.bcoeff is not None:
                        self.xmb = _expma(stx,self.xmb,self.bcoeff)
                    self.series.appendleft([stx,self.xma,self.xmb])
                    self._pop()


class XDIFF(Metric):

    def __init__(self,c1,c2,minpts):
        Metric.__init__(self)
        self.c1 = c1
        self.c2 = c2
        self.minpts = minpts
        self.xma1 = None
        self.xma2 = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.xma1 = None
        self.xma2 = None
        self.count = 0

    def push(self, price):
        self.price = price
        self.count += 1
        self.calc()

    def calc(self):
        self.xma1 = _expma(self.price,self.xma1,self.c1)
        self.xma2 = _expma(self.price,self.xma2,self.c2)
        if self.count >= self.minpts:
            diff = self.xma1 - self.xma2
            pdiff = 0
            if self.xma2 > 0: pdiff = self.xma1/self.xma2 - 1
            vec = (self.xma1, self.xma2, diff, pdiff)
            self.series.appendleft(vec)
            self._pop()

class XMA(Metric):

    def __init__(self,coeff,minpts):
        Metric.__init__(self)
        self.coeff = coeff
        self.minpts = minpts
        self.xma = None
        self.count = 0
        self.base = None

    def reset(self):
        Metric.reset(self)
        self.xma = None
        self.count = 0

    def push(self, price):
        self.price = price
        self.count += 1
        self.calc()

    def setprecision(self, p):
        if p > 0: self.base = float(10 ** p)

    def calc(self):
        self.xma = _expma(self.price,self.xma,self.coeff)
        if self.base is not None: self.xma = int(self.xma * self.base)/self.base
        if self.count >= self.minpts:
            self.series.appendleft(self.xma)
            self._pop()

    def dump(self,filename):
        try:
            f = open(filename,"w")
            print >> f, "XMA", self.xma
            print >> f, "COUNT", self.count
            f.close()
        except:
            print >> sys.stderr, "ERROR: unable to write indicator init file: %s" % filename

    def load(self,filename):
        try:
            f = open(filename,"r")
        except:
            print >> sys.stderr, "WARNING: unable to load indicator init file: %s" % filename
        else:
            for j in f:
                j = j[:-1]
                tag, data = j.split()
                v = float(data)
                if tag == "XMA": self.xma = v
                if tag == "COUNT": self.count = v
            f.close()
            self.series.clear()
            if self.xma is not None:
                self.series.appendleft(self.xma)

class SMA(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        u = _average(self.prices,self.length)
        self.series.appendleft(u)
        self._pop()

class MEDIAN(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        u = _median(self.prices,self.length)
        self.series.appendleft(u)
        self._pop()

class MAD(Metric):

    def __init__(self,coeff,minpts):
        Metric.__init__(self)
        self.coeff = coeff
        self.minpts = minpts
        self.xma = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.xma = None
        self.count = 0

    def push(self, price):
        self.price = price
        self.count += 1
        self.calc()

    def calc(self):
        self.xma = _expma(self.price,self.xma,self.coeff)
        if self.count >= self.minpts:
            if self.price != 0:
                mad = 100.0 * (self.price - self.xma)/self.price
                self.series.appendleft(mad)
                self._pop()


class STAT(Metric):

    def __init__(self,limit=100):
        Metric.__init__(self)
        self.prices = deque()
        self.limit = limit

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) > self.limit:
            self.prices.pop()

    def average(self, length):
        u = _average(self.prices,length)
        return u

    def max(self, length):
        tmp = list(self.prices)[:length]
        return max(tmp);

    def min(self, length):
        tmp = list(self.prices)[:length]
        return min(tmp);

    def median(self,length):
        tmp = list(self.prices)
        tmp = tmp[:length]
        tmp.sort()
        n = int(length/2)
        return tmp[n]

    def stdev(self, length):
        avg = _average(self.prices,length)
        lst = list(self.prices)[:length]
        cnt = sum = 0
        vv = None
        std = None
        if len(lst) > 0:
            for x in lst:
                if x is not None:
                    sum += (x - avg)*(x-avg)
                    cnt += 1
            if cnt > 0: vv = sum/cnt
            if vv is not None: std = math.sqrt(vv)
        return std

    def zscore(self, length):
        v = self.prices[0]
        m = self.average(length)
        std = self.stdev(length)
        z = None
        if std is not None and std > 0 and m is not None: z = float(v-m)/std
        return z

    def size(self):
        return len(self.prices)


class MO(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        a,b = (self.prices[0],self.prices[self.length-1])
        u = a - b
        r = 0
        if b != 0: r = u / float(b)
        vec = (u,r)
        self.series.appendleft(vec)
        self._pop()

class LOGRT(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        a,b = (self.prices[0],self.prices[self.length-1])
        r = 0
        if b != 0: r = math.log(a/b)
        self.series.appendleft(r)
        self._pop()

class AMO(Metric):

    def __init__(self,length,avglen,abs=False):
        Metric.__init__(self)
        self.length = length
        self.avglen = avglen
        self.prices = deque()
        self.mo = deque()
        self.abs = abs

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.mo.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        a,b = (self.prices[0],self.prices[self.length-1])
        u = a - b
        if self.abs and u < 0: u = -u
        self.mo.appendleft(u)
        if len(self.mo) >= self.avglen:
            x = _average(self.mo,self.avglen)
            self.series.appendleft(x)
            self.mo.pop()
            self._pop()

class XMO(Metric):

    def __init__(self,length,c1,c2,minpts):
        Metric.__init__(self)
        self.length = length
        self.c1 = c1
        self.c2 = c2
        self.xma1 = self.xma2 = None
        self.minpts = minpts
        self.prices = deque()
        self.count = 0
        self.raw = None
        self.useRoc = False
        self.useAbs = False

    def reset(self):
        Metric.reset(self)
        self.xma1 = self.xma2 = None
        self.prices.clear()
        self.count = 0
        self.raw = None

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.count += 1
            self.calc()
            self.prices.pop()

    def calc(self):
        self.raw = self.prices[0] - self.prices[self.length-1]
        if self.useRoc:
            rw = 0
            refpt = self.prices[self.length-1]
            if refpt != 0: rw = self.raw/float(refpt)
            self.raw = rw
        if self.useAbs: self.raw = math.fabs(self.raw)
        self.xma1 = _expma(self.raw,self.xma1,self.c1)
        self.xma2 = _expma(self.xma1,self.xma2,self.c2)
        if self.count >= self.minpts:
            self.series.appendleft([self.raw,self.xma1,self.xma2])
            self._pop()

    def useROC(self,flag):
        self.useRoc = flag

    def useABS(self,flag):
        self.useAbs = flag

    def dump(self,filename):
        try:
            f = open(filename,"w")
            for p in self.prices:
                print >> f, "PRICE", p
            print >> f, "XMA1", self.xma1
            print >> f, "XMA2", self.xma2
            print >> f, "COUNT", self.count
            if self.count >= self.minpts: print >> f, "U", self.raw
            f.close()
        except:
            print >> sys.stderr, "ERROR: unable to write indicator init file: %s" % filename

    def load(self,filename):

        try:
            f = open(filename,"r")
        except:
            print >> sys.stderr, "WARNING: unable to load indicator init file: %s" % filename
        else:
            self.prices.clear()
            u = None
            for j in f:
                j = j[:-1]
                tag, data = j.split()
                v = float(data)
                if tag == "PRICE": self.prices.append(v)
                if tag == "XMA1": self.xma1 = v
                if tag == "XMA2": self.xma2 = v
                if tag == "COUNT": self.count = v
                if tag == "U": u = v
            f.close()
            self.series.clear()
            if u is not None:
                self.series.appendleft([u,self.xma1,self.xma2])


class BOX(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        tmp = list(self.prices)
        hi = max(tmp)
        lo = min(tmp)
        pct = 0.50
        if (hi-lo) != 0: pct = (self.prices[0] - lo)/(hi-lo)
        vec = (pct,hi,lo)
        self.series.appendleft(vec)
        self._pop()


class HILO(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()
        self.lowest = self.highest = False
        self.highs = self.lows = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.lowest = self.highest = False

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def atLow(self):
        return self.lowest

    def atHigh(self):
        return self.highest

    def calc(self):
        self.lowest = self.highest = False
        tmp = list(self.prices)
        highs = unpack(tmp,1)
        lows = unpack(tmp,2)
        self.highs = highs[:self.length]
        hi = max(self.highs)
        self.lows = lows[:self.length]
        lo = min(self.lows)
        vec = (hi,lo)
        if hi == highs[0]: self.highest = True
        if lo == lows[0]: self.lowest = True
        self.series.appendleft(vec)
        self._pop()


### PT - peak/trough object
### resets to anchor
class PT(Metric):

    def __init__(self):
        Metric.__init__(self)
        self.peak = self.trough = None

    def reset(self):
        Metric.reset(self)
        self.peak = self.trough = None

    def anchor(self,base):
        self.base = base
        self.peak = self.trough = None
        self.series.clear()
        self.push(base)

    def push(self, price):
        changed = False

        ### handles if you pass it a pricebar vector
        lo = hi = None
        try:
            hi = price[1]
            lo = price[2]
        except:
            lo = hi = price

        if self.peak is None or hi > self.peak:
            self.peak = hi
            changed = True
        if self.trough is None or lo < self.trough:
            self.trough = lo
            changed = True
        if changed:
            self.series.appendleft([self.trough,self.peak])
            self._pop()


class Highest(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        tmp = list(self.prices)
        hi = max(tmp[:self.length])
        self.series.appendleft(hi)
        self._pop()

class Lowest(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.length = length
        self.prices = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.length:
            self.calc()
            self.prices.pop()

    def calc(self):
        tmp = list(self.prices)
        lo = min(tmp[:self.length])
        self.series.appendleft(lo)
        self._pop()


class MACD(Metric):


    def __init__(self,c1,c2,minpts):
        Metric.__init__(self)
        self.c1, self.c2 = (c1,c2)
        self.minpts = minpts
        self.price = None
        self.count = 0
        self.xma1 = self.xma2 = self.xma3 = None

    def reset(self):
        Metric.reset(self)
        self.price = None
        self.count = 0
        self.xma1 = self.xma2 = self.xma3 = None

    def push(self, price):
        self.price = price
        self.count += 1
        self.calc()

    def calc(self):
        p = self.price
        self.xma1 = _expma(p,self.xma1,self.c1)
        self.xma2 = _expma(p,self.xma2,self.c2)
        if self.count >= self.minpts:
           mac = self.xma1 - self.xma2
           self.xma3 = _expma(mac,self.xma3,0.20)
           self.series.appendleft((mac,self.xma3))
           self._pop()

class SMACD(Metric):

    def __init__(self,c1,c2,c3):
        Metric.__init__(self)
        self.c1, self.c2, self.c3 = (c1,c2,c3)
        self.prices = deque()
        self.macs = deque()
        self.sma1 = self.sma2 = self.sma3 = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.macs.clear()
        self.sma1 = self.sma2 = self.sma3 = None

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > max(self.c1,self.c2):
            self.sma1 = _average(self.prices,self.c1)
            self.sma2 = _average(self.prices,self.c2)
            mac = self.sma1 - self.sma2
            self.macs.appendleft(mac)
            if len(self.macs) > self.c3:
                self.sma3 = _average(self.macs,self.c3)
                sig = mac - self.sma3
                self.series.appendleft((mac,sig))
                self._pop()

class STOCH(Metric):

    def __init__(self,width,len1,len2):
        Metric.__init__(self)
        self.width, self.len1, self.len2 = (width,len1,len2)
        self.minpts = width + len1 + len2
        self.prices = deque()
        self.k = deque()
        self.d = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.k.clear()
        self.d.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.width:
            self.calc()
            self.prices.pop()

    def calc(self):
        width = self.width
        tmp = list(self.prices)
        highs = unpack(tmp,1)
        lows = unpack(tmp,2)
        closes = unpack(tmp,3)
        hi,lo = (max(highs[:width]),min(lows[:width]))
        r = hi - lo
        v= 0.5
        if r > 0: v = (closes[0] - lo)/r
        self.k.appendleft(v)
        if len(self.k) >= self.len1:
            u = _average(self.k,self.len1)
            self.d.appendleft(u)
            if len(self.d) >= self.len2:
                w = _average(self.d,self.len2)
                ### v = %K, u = %D, w = slow %D
                vec = (v,u,w)
                self.series.appendleft(vec)
                self._pop()

class LOKI(Metric):

    ### stoch on single values

    def __init__(self,width,len1,len2):
        Metric.__init__(self)
        self.width, self.len1, self.len2 = (width,len1,len2)
        self.minpts = width + len1 + len2
        self.prices = deque()
        self.k = deque()
        self.d = deque()

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.k.clear()
        self.d.clear()

    def push(self, price):
        self.prices.appendleft(price)
        if len(self.prices) >= self.width:
            self.calc()
            self.prices.pop()

    def calc(self):
        width = self.width
        tmp = list(self.prices)
        hi,lo = (max(tmp[:width]),min(tmp[:width]))
        r = hi - lo
        v= 0.5
        if r > 0: v = (tmp[0] - lo)/r
        self.k.appendleft(v)
        if len(self.k) >= self.len1:
            u = _average(self.k,self.len1)
            self.d.appendleft(u)
            if len(self.d) >= self.len2:
                w = _average(self.d,self.len2)
                ### v = %K, u = %D, w = slow %D
                vec = (v,u,w)
                self.series.appendleft(vec)
                self._pop()

class ADV(Metric):

    def __init__(self,coeff,minpts):
        Metric.__init__(self)
        self.coeff = coeff
        self.minpts = minpts
        self.prices = deque()
        self.xma = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.xma = None

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            prev = self.prices[1][3]
            top, bot = (max(hi,prev),min(lo,prev))
            a = top - opn
            b = close - bot
            r = top - bot
            y = 0.50
            if r > 0: y = (a+b)/(2.0*r)
            self.xma = _expma(y,self.xma,self.coeff)
            if len(self.prices) >= self.minpts:
                vec = (y,self.xma)
                self.series.appendleft(vec)
                self._pop()
                self.prices.pop()

class Trendi(Metric):


    def __init__(self,coeff,minpts):
        Metric.__init__(self)
        self.coeff = coeff
        self.minpts = minpts
        self.prices = deque()
        self.xma1 = self.xma2 = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.xma1 = self.xma2 = None

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            prev = self.prices[1][3]
            top, bot = (max(hi,prev),min(lo,prev))
            r = top - bot
            ch = close - prev
            self.xma1 = _expma(ch,self.xma1,self.coeff)
            self.xma2 = _expma(r,self.xma2,self.coeff)
            if len(self.prices) > self.minpts:
                assert(self.xma2 > 0)
                y = self.xma1/self.xma2
                self.series.appendleft(y)
                self._pop()
                self.prices.pop()

class ATR(Metric):


    def __init__(self,length):
        Metric.__init__(self)
        self.prices = deque()
        self.rvals = deque()
        self.length = length

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.rvals.clear()

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            prev = self.prices[1][3]
            top, bot = (max(hi,prev),min(lo,prev))
            r = top - bot
            self.rvals.appendleft(r)
            if len(self.rvals) >= self.length:
                avg = _average(self.rvals,self.length)
                med = _median(self.rvals,self.length)
                v = (avg,med)
                self.series.appendleft(v)
                self._pop()
                self.prices.pop()
                self.rvals.pop()

### price range index
### give position of current close relative to a defined range
### like loki - but works on TrueRange and take a smoothing coeff
class PRI(Metric):

    def __init__(self,width,coeff):
        Metric.__init__(self)
        self.prices = deque()
        self.tops = deque()
        self.bots = deque()
        self.width = width
        self.coeff = coeff
        self.xvr = None

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.tops.clear()
        self.bots.clear()
        self.xvr = None

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, lst = self.prices[0]
            prev = self.prices[1][3]
            top, bot = (max(hi,prev),min(lo,prev))
            self.tops.appendleft(top)
            self.bots.appendleft(bot)
            if len(self.tops) >= self.width:
                tt = max(list(self.tops)[:self.width])
                bb = min(list(self.bots)[:self.width])
                r = float(tt - bb)
                xv = 0.50
                if r > 0: xv = (lst - bb)/r
                self.xvr = _expma(xv,self.xvr,self.coeff)
                v = (xv, self.xvr)
                self.series.appendleft(v)
                self._pop()
                self.prices.pop()
                self.tops.pop()
                self.bots.pop()


## congestion index
## 100 - choppy market, 0 = very trendy market
class CXI(Metric):

    def __init__(self,length):
        Metric.__init__(self)
        self.prices = deque()
        self.rvals = deque()
        self.length = length

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.rvals.clear()

    def push(self, pricevector):
        self.prices.appendleft(pricevector)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            prev = self.prices[1][3]
            top, bot = (max(hi,prev),min(lo,prev))
            r = top - bot
            self.rvals.appendleft(r)
            if len(self.rvals) >= self.length:
                ### get sum of ATRs
                tot = sum(list(self.rvals)[:self.length])

                ### get H/L range of total span
                pp = list(self.prices)[:self.length]
                hipt = max([x[1] for x in pp])
                lopt = min([x[2] for x in pp])
                bigr = hipt - lopt
                raw = 0
                if bigr != 0:
                    raw = tot/bigr
                    cxi = 100 * (math.log(raw)/math.log(self.length*1.0))
                    self.series.appendleft(cxi)
                    self._pop()
                    self.prices.pop()
                    self.rvals.pop()

class RUN(Metric):

    ### consecutive run of N times, of minimum size Q

    def __init__(self,typ,cnt,minsize):
        assert(typ == "HIGH" or typ == "LOW" or typ == "LAST")
        Metric.__init__(self)
        self.prices = deque()
        self.typ = typ
        self.cnt = cnt
        self.minsize = minsize

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        if isinstance(price,PriceBar):
            self.prices.appendleft(price)
            self.calc()
        else:
            raise MetricError("PriceBar object needed")

    def calc(self):
        if len(self.prices) > self.cnt:
            prices = self.prices

            if self.typ == "LOW":
                cond = True
                for j in range(1,self.cnt+1):
                    d = prices[j].low - prices[j-1].low
                    if d < self.minsize:
                        cond = False
                        break
                self.series.appendleft(cond)
                self.prices.pop()
                self._pop()

            if self.typ == "HIGH":
                cond = True
                for j in range(1,self.cnt+1):
                    d = prices[j-1].high - prices[j].high
                    if d < self.minsize:
                        cond = False
                        break
                self.series.appendleft(cond)
                self.prices.pop()
                self._pop()

            if self.typ == "LAST":
                cond = True
                for j in range(1,self.cnt+1):
                    d = prices[j-1].last - prices[j].last
                    if d < self.minsize:
                        cond = False
                        break
                self.series.appendleft(cond)
                self.prices.pop()
                self._pop()


class PULLBK(Metric):

    ### buyers pullback

    def __init__(self,typ):
        assert(typ == "HIGH" or typ == "LOW")
        Metric.__init__(self)
        self.prices = deque()
        self.typ = typ

    def reset(self):
        Metric.reset(self)
        self.prices.clear()

    def push(self, price):
        if isinstance(price,PriceBar):
            self.prices.appendleft(price)
            self.calc()
        else:
            raise MetricError("PriceBar object needed")

    def calc(self):
        if len(self.prices) > 3:
            prices = self.prices

            if self.typ == "LOW":
                cond = prices[0].low < prices[1].low and prices[1].low < prices[2].low
                cond = cond and prices[0].high < prices[1].high and prices[1].high < prices[2].high
                cond = cond and prices[0].last < prices[1].last and prices[1].last < prices[2].last
                cond = cond and prices[2].last < prices[3].last

                ### look at the dip value when cond = True, the filter dip >= some value
                dip = (prices[2].low - prices[0].low)/prices[2].low
                vec = (dip,cond)
                self.series.appendleft(vec)
                self.prices.pop()
                self._pop()

            if self.typ == "HIGH":
                cond = prices[0].high > prices[1].high and prices[1].high > prices[2].high
                cond = cond and prices[0].low > prices[1].low and prices[1].low > prices[2].low
                cond = cond and prices[0].last > prices[1].last and prices[1].last > prices[2].last
                cond = cond and prices[2].last > prices[3].last

                ### look at the dip value when cond = True, the filter dip >= some value
                dip = (prices[0].high - prices[2].high)/prices[2].high
                vec = (dip,cond)
                self.series.appendleft(vec)
                self.prices.pop()
                self._pop()


class ADX(Metric):


    def __init__(self,c0,c1,minpts):
        Metric.__init__(self)
        self.prices = deque()
        self.vals = deque()
        self.c0 = c0
        self.c1 = c1
        self.minpts = int(minpts)
        self.adx = self.upx = self.dnx = self.trx = None
        self.count = 0

    def reset(self):
        Metric.reset(self)
        self.prices.clear()
        self.vals.clear()
        self.adx = self.upx = self.dnx = self.trx = None
        self.count = 0

    def push(self, price):
        self.prices.appendleft(price)
        self.calc()

    def calc(self):
        if len(self.prices) > 1:
            opn, hi, lo, close = self.prices[0]
            opn2, hi2, lo2, prev = self.prices[1]
            #top, bot = (max(hi,prev),min(lo,prev))
            #r = top - bot
            up = hi-hi2
            dn = lo2-lo
            x = y = 0
            if ( up > 0 and up > dn ): x = up
            if ( dn > 0 and dn > up ): y = dn
            self.upx = _expma(x,self.upx,self.c0)
            self.dnx = _expma(y,self.dnx,self.c0)
            #self.trx = _expma(r,self.trx,self.c0)
            self.count += 1
            if self.count >= self.minpts:
                if (self.upx+self.dnx) > 0:
                    dx = math.fabs(self.upx-self.dnx)/(self.upx+self.dnx)
                    self.adx = _expma(dx,self.adx,self.c1)
                    self.series.appendleft((self.adx,dx))
                    self._pop()
                    self.prices.pop()



### general stop object
### setup:
###  set_fixed(fixed stop amt, array of 'steps')
###         each array index holds the multiplier to be used in calculating the stop of the trade maximum
###         ie. fixed stop = 0.10 and fixed array [1,1.5,0.5]
###                 - trade maximun <= 0.10 will have 0.10 stop of the high  ( = 1 * .10)
###                 - trade maximun > 0.10 and <= 0.20 ill have 0.15 stop of the high ( = 1.5 * 0.10)
###                 - trade maximun > 0.20 will have 0.05 stop of the high = ( 0.5 * 10)
###             - fixed amt defines the stepsize and stop, the index of the array defines the steplevel
###             - and the value at steps[i] defines the multiplier to the stop amt
###         i.e note: a fixed stop = set_fixed(amt,[1])
###  set_atr(atrlen, array of steps)
###     - same as fixed, but based on median volatility give by ATR(atrlen)
###  set_trail(trailing stop len)
###     - calcs a trailing N bar stop
###
###  object.stops = list containing [fixedStop, volStop, trailingStop]
###  object.best() = returns the closest stop
###  object.worst() = returns the farthest stop
###  object.push() = takes a pricebar.vector() for ATR, trailing calcs
###  object.update() = takes current bid offer and calculated the NEXT set of stops
###     (as to not mar current stops if they haven't been checked yet)
###  object.entry() = set the entry position and price of the trade
###  object.location = deque that hold the pct position of the trade relative to its highest point
###     object.location[0] gives the current location of the trade
###  object.high = trade's highest price
###  object.low = trade's lowest price
###

class STOP:

    def __init__(self, default):
        self.position = self.entryprc = 0
        self.fixed = self.fsteps = None
        self.atr = self.vsteps = None
        self.atr_mult=1
        self.high = self.low = None
        self.hilo = None
        self.location = deque()
        self.stops = self.next = None
        self.default = default

    def push(self, pricevector):
        if self.hilo is not None: self.hilo.push(pricevector)
        if self.atr is not None: self.atr.push(pricevector)

    def set_entry(self, pos, price):
        self.position = pos
        self.entryprc = self.high = self.low = price
        self.stops = self._calcStops()
        self.next = None
        self.location.clear()

    def clear(self):
        self.position = self.entryprc = 0
        self.high = self.low = None
        self.stops = self.next = None
        self.location.clear()

    def best(self):
        b = None
        tmp = [ x for x in self.stops if x > 0 ]
        if self.position > 0 and len(tmp) > 0: b = max(tmp)
        if self.position < 0 and len(tmp) > 0: b = min(tmp)
        if b is None:
           if self.position > 0: b = self.entryprc - self.default
           if self.position < 0: b = self.entryprc + self.default
        return b

    def worst(self):
        b = None
        tmp = [ x for x in self.stops if x > 0 ]
        if self.position > 0 and len(tmp) > 0: b = min(tmp)
        if self.position < 0 and len(tmp) > 0: b = max(tmp)
        if b is None:
           if self.position > 0: b = self.entryprc - self.default
           if self.position < 0: b = self.entryprc + self.default
        return b

    def set_fixed(self, fixedamt, steps=None):
        self.fixed = fixedamt
        self.fsteps = steps

    def set_atr(self, atrlen, steps=None, mult=1):
        self.atr = ATR(atrlen)
        self.atr_mult = mult
        self.vsteps = steps

    def set_trail(self,tlen):
        self.hilo = HILO(tlen)

    def _calcStops(self):

        fixed = vol = trail = 0

        if self.position > 0:
            m = max(self.high - self.entryprc,0)

            if self.fixed is not None:
                fixed = self.entryprc - self.fixed
                if self.fsteps is not None:
                    i = int(m/self.fixed)
                    if i >= len(self.fsteps): i = -1
                    fixed = self.high - self.fixed*self.fsteps[i]

            if self.atr is not None and self.atr.size() > 0:
                median = self.atr[0][1]
                vol = self.entryprc - median*self.atr_mult
                if self.vsteps is not None:
                    i = int(m/median)
                    if i >= len(self.vsteps): i = -1
                    vol = self.high - median*self.vsteps[i]

            if self.hilo is not None and self.hilo.size() > 0:
                if not self.hilo.atLow():
                    trail = self.hilo[0][1]

        if self.position < 0:
            m = max(self.entryprc - self.low,0)

            if self.fixed is not None:
                fixed = self.entryprc + self.fixed
                if self.fsteps is not None:
                    i = int(m/self.fixed)
                    if i >= len(self.fsteps): i = -1
                    fixed = self.low + self.fixed*self.fsteps[i]

            if self.atr is not None and self.atr.size() > 0:
                median = self.atr[0][1]
                vol = self.entryprc + median*self.atr_mult
                if self.vsteps is not None:
                    i = int(m/median)
                    if i >= len(self.vsteps): i = -1
                    vol = self.low + median*self.vsteps[i]

            if self.hilo is not None and self.hilo.size() > 0:
                if not self.hilo.atHigh():
                    trail = self.hilo[0][0]

        return [fixed,vol,trail]


    ### monitor position versus current prices
    def update(self, bid, offer):

        if self.position == 0: return

        mid = 0.5 * (bid+offer)
        if self.high is None or mid > self.high: self.high = mid
        if self.low is None or mid < self.low: self.low = mid

        loc = 0
        if self.position > 0:
            if mid > self.entryprc: loc = (mid-self.entryprc)/float(self.high-self.entryprc)

        if self.position < 0:
            if mid < self.entryprc: loc = (self.entryprc-mid)/float(self.entryprc-self.low)

        self.location.appendleft(loc)

        ### improve stops if new calculated values are better
        if self.next is not None:
            for i,v in enumerate(self.next):
                if self.position > 0:
                    if v > self.stops[i] and v > 0: self.stops[i] = v
                if self.position < 0:
                    if v < self.stops[i] and v > 0: self.stops[i] = v

        self.next = self._calcStops()



if __name__ == "__main__":

    c = 0
    p = PriceBar()
    v1 = 2.0/13
    v2 = 2.0/7
    x = TSI(v1,v2,10)
    xsig = SMA(5)
    f = open("../testdata/20100311.DIA.csv","r")
    hdr = f.readline()
    for line in f:
        line = line[:-1]
        s = line.split(",")
        bid = float(s[2])
        ask = float(s[3])
        mid = (bid+ask)/2.0

        p.collect(mid)
        if (c+1) % 60 == 0:
            bar = p.vector()
            x.push(bar[3])
            if x.size() > 0:
                xsig.push(x[0])
                if xsig.size() > 0:
                    print "%s %7.3f %7.3f" % (p,x[0],xsig[0])
                else:
                    print p
            p.clear()
        c = c + 1


