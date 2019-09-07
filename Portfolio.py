
import logging
from threading import Thread, Lock
from MarketObjects import Order, Fill, Position
from ConfigParser import SafeConfigParser
from DataQueues import DQueue
import pandas
import cPickle
import datetime

'''
Portfolio is the gatekeeper of all Strategy to Exchange communication.
It is capabble of handling multiple strategies at one time (use the add() method)
The Porfolio class' functions are:
    1. Marshall all order and fill flow from the Exchange to all strategies
    2. Do accounting for all trade activity and pnl reporting
        - at the symbol level
        - at the strategy level
        - and a composite 'portofolio' level that combines all strategies activity
    3. Provides summary stats in simulations and optimazations
        - stats()  output can been write to pickle and Excel files
'''

class Portfolio(Thread):

    def __init__(self,name,config_file):

        super(Portfolio,self).__init__()

        self.portfolio_name = name
        self.running = True # thread flag
        self.lock = Lock()

        self.current_timestamp = None

        # queues mapped by strategy name
        self.STRAT_orders = {}
        self.order_lookup = {}

        ## disabled for new Strategy/Exchange/Portfolio configuration
        ##self.OUT_orders = DQueue()
        self.OUT_orders = None 

        ## disabled for new Strategy/Exchange/Portfolio configuration
        ## self.IN_fills = DQueue()
        self.IN_fills = None 

        ## strategy attributes for reporting purposes
        self.strategy_attributes = {}

        ## holds posns by individual strategy
        self.strategy_positions = {}
        self.strategy_allocations = {} ##  tuple(portfolio_weight, dollars_allocated)

        # convert this array of dict(symbol,qty,mtm,owner,timestamp) to df for analysis
        self.trading_activity = {}
        self.equity_curves = {}

        self.capital = 0 ## global wallet


        ## map of current market data by symbol
        self.current_data = {}

        ## portfolio dict that holds aggregate positions across all strats
        self.strategy_positions[self.portfolio_name] = {}
        self.trading_activity[self.portfolio_name] = {}
        self.equity_curves[self.portfolio_name] = {}


        self._attributes = {}           ## general config dict

        self.path = '.'  ## data dump path

        self.log = logging.getLogger(__name__)

        if config_file:
            self.config_file = config_file
            self.load_config(self.config_file)

        ## data structure to save pickled results
        self.storage = {}
        for k in ['settings', 'trades','trade_summary','curve','curve_stats']:
            self.storage[k] = dict()


    def load_config(self,config):
        parser = SafeConfigParser()
        parser.read(config)
        self.log.info('Loading config: %s' % config)



    ##NOTE that add() takes something that looks like the strategy
    ##an interface that provides the name and queue connecitions for the strategy
    ##this allow distributed placement of actual strategies
    def add(self,strategy):
        # dict[strategy][symbol] = []  #array of dicts that can be converted to df
        self.strategy_positions[strategy.name] = {}
        self.equity_curves[strategy.name] = {}
        self.trading_activity[strategy.name] = {}

        self.strategy_attributes[strategy.name] = dict(strategy.strategy_params)

        self.STRAT_orders[strategy.name] = strategy.OUT_orders.new()


    def update_allocations(self,alloc):

        self.capital += alloc
        allocs = set(self.strategy_allocations.keys())
        if allocs:
            ## use indicated allocations
            for strategy in allocs:
                wgt, dollars = self.strategy_allocations[strategy]
                dollars = int(self.capital * wgt)
                self.strategy_allocations[strategy] = (wgt,dollars)
        else:
            ## use equal paritioning
            wgt = 1.0/len(strats)
            dollars = int(self.capital*wgt)
            for strategy in strats:
                self.strategy_allocations[strategy] = (wgt,dollars)


    def normalize_pnl(self,symbol,ticks):
        return ticks


    '''
    def normalize_pnl(self,symbol,ticks):

        if ticks == None:
            return None

        key = 'Default'
        if symbol in self.symbol_attributes.keys():
            key = symbol

        try:
            if self._attributes['Portfolio']['show_dollar_pnl'] == 'True':
                tks = self.symbol_attributes[key]['tick_size']
                dollar_value = self.symbol_attributes[key]['dollar_value']
                dollar_pnl = ticks * (dollar_value/tks)
                return dollar_pnl
            else:
                return ticks
        except:
            return ticks
    '''


    def profit_loss(self,ticks,qty_left,fill,owner):

        pnl = self.normalize_pnl(fill.symbol,ticks)

        trade = {
            'symbol': fill.symbol,
            'qty':fill.qty if fill.side == Order.BUY else -fill.qty,
            'price':fill.price,
            'pnl':pnl,
            'owner':owner,
            'timestamp':fill.timestamp
        }
        activity = self.trading_activity[owner]
        if fill.symbol not in activity.keys(): activity[fill.symbol] = []
        activity[fill.symbol].append(trade)
        self.log.info("trade: %s" % trade)

        curves = self.equity_curves[owner]
        if fill.symbol not in curves.keys(): curves[fill.symbol] = []
        equ = curves[fill.symbol]
        prev_pnl = 0
        if equ: prev_pnl = equ[-1]['realized_pnl']
        if not pnl: pnl = 0

        snapshot = {
            'symbol':fill.symbol,
            'qty':qty_left,
            'mtm':pnl,
            'realized_pnl':prev_pnl + pnl,
            'mtm_pnl':prev_pnl + pnl,
            'owner':owner,
            'timestamp':fill.timestamp
        }

        equ.append(snapshot)
        self.log.info("pnl snap: %s" % snapshot)

        ##self.update_allocations(pnl)


    def mark_position(self, price_data, owner, position):
        mtm = prev_pnl = 0
        qty = 0
        symbol = price_data.symbol

        if position:
            qty = position.qty
            mtm_price = price_data.close
            if qty > 0:
                if price_data.bid: mtm_price = price_data.bid
                mtm = self.normalize_pnl(symbol, qty*(mtm_price - position.price))
            if qty < 0:
                if price_data.ask: mtm_price = price_data.ask
                mtm = self.normalize_pnl(symbol, abs(qty)*(position.price - mtm_price))

        curves = self.equity_curves[owner]
        if symbol not in curves.keys(): curves[symbol] = []
        equ = curves[symbol]
        prev_pnl = 0
        if equ: prev_pnl = equ[-1]['realized_pnl']

        snapshot = {
            'symbol':symbol,
            'qty':qty,
            'mtm':mtm,
            'realized_pnl':prev_pnl,
            'mtm_pnl':prev_pnl + mtm,
            'owner':owner,
            'timestamp':price_data.timestamp
        }

        
        ## make sure pnl snapshots due to trading come after
        ## mtm snapshots of at the same timestamp.
        ## duplicate timestamps will be reduced out when blending the curves
              
        last = None 
        if equ:
            if equ[-1]['timestamp'] == snapshot['timestamp']:
                last = equ.pop()

        equ.append(snapshot)
        if last: equ.append(last)

        self.log.info("mtm snap: %s" % snapshot)


    def update_positions(self, symbol, fill, strategy_owner):

        ## update owner stats, and net portfolio stats
        for owner in [strategy_owner, self.portfolio_name]:

            positions = self.strategy_positions[owner]
            position = positions.get(symbol, None)
            vqty = vwp = 0
            if position:
                vqty, vwp = position.qty, position.price

            #longs
            if vqty > 0:
                # BUYS
                if fill.side == Order.BUY:
                    # add longMarketMessage
                    vwp = (vqty * vwp) + (fill.price * fill.qty)
                    vqty += fill.qty
                    vwp = vwp/float(vqty)
                    self.profit_loss(None,vqty,fill,owner)     #mark new position
                else:
                # SELLS
                    if vqty >= fill.qty:
                        # reduce long
                        vqty -= fill.qty
                        self.profit_loss(fill.qty * (fill.price - vwp),vqty,fill,owner)
                    else:
                        # become net short
                        qty_left = vqty - fill.qty
                        self.profit_loss(vqty * (fill.price - vwp),qty_left,fill,owner)
                        vqty = qty_left
                        vwp = fill.price
            #shorts
            elif vqty < 0:
                if fill.side == Order.SELL:
                    # add short
                    vwp = (-vqty * vwp) + (fill.price * fill.qty)
                    vqty -= fill.qty
                    vwp = -vwp/float(vqty)
                    self.profit_loss(None,vqty,fill,owner)     #mark new position
                else:
                    # reduce short
                    if abs(vqty) >= fill.qty:
                        vqty += fill.qty
                        self.profit_loss(fill.qty * (vwp - fill.price),vqty,fill,owner)
                    else:
                        # become net long
                        qty_left = vqty + fill.qty
                        self.profit_loss(abs(vqty) * (vwp - fill.price),qty_left,fill,owner)
                        vqty = qty_left
                        vwp = fill.price
            #flat
            elif vqty == 0:
                vqty = fill.qty
                if fill.side == Order.SELL: vqty = -fill.qty
                vwp = fill.price
                self.profit_loss(None,vqty,fill,owner)     #mark new position

            self.strategy_positions[owner][symbol] = Position(symbol,vqty,vwp)
            self.log.info("strategy %s: updated posn: %s" % (owner,self.strategy_positions[owner][symbol]) )


    def mark_to_market(self, market_data):

        symbol = market_data.symbol
        for strategy, positions in self.strategy_positions.iteritems():
            if symbol in positions.keys():
                self.mark_position(market_data,strategy,positions[symbol])
            else:
                ## propogate last curve point to sync with price history
                self.mark_position(market_data,strategy,None)


    def _trunc_results(self,dct,exclude=[]):
        for k, v in dct.iteritems():
            try:
                if k not in exclude:
                    dct[k]= int(v * 10000)/10000.0
            except:
                pass
        return dct

    def win_loss_stats(self,tag,stat_table):

        if stat_table.empty:
            return dict(tag=tag,cnt=0,w_avg=0,w_std=0,pr=0,l_avg=0,l_std=0,w_pct=0,pnl=0,shrp=0)

        wins = stat_table[stat_table['pnl'] > 0]
        losses = stat_table[stat_table['pnl'] <= 0]
        trades = stat_table[~pandas.isnull(stat_table['pnl'])] ## grab all not null pnls
        sharpe = 0
        if trades['pnl'].count() >0:
            sharpe = trades['pnl'].mean()/trades['pnl'].std()
        avg_win = stdv_win = 0
        if wins['pnl'].count() > 0:
            avg_win, stdv_win = wins['pnl'].mean(), wins['pnl'].std()
        avg_loss = stdv_loss = 0
        if losses['pnl'].count() > 0:
            avg_loss, stdv_loss = losses['pnl'].mean(), losses['pnl'].std()
        profit_ratio = 0
        if avg_loss != 0:
            profit_ratio = -1*avg_win/avg_loss
        cnt = stat_table['pnl'].count()
        tot = stat_table['pnl'].sum()
        wpct = 0
        if cnt > 0:
            wpct = float(wins['pnl'].count())/cnt

        dct = dict(tag=tag,cnt=cnt,w_avg=avg_win,w_std=stdv_win,pr=profit_ratio, \
                   l_avg=avg_loss,l_std=stdv_loss,w_pct=wpct,pnl=tot,shrp=sharpe)

        return self._trunc_results(dct,exclude=['tag','cnt','pnl'])


    def equ_curve_stats(self,tag,curve_table):

        if curve_table.empty:
            return dict(tag=tag,mtm_pnl=0,max_equ=0,max_dd=0,avg_dd=0)

        max_equ = 0
        max_dd = avg_dd  = 0
        mtm_pnl = 0
        if curve_table['mtm_pnl'].count() > 0:
            curve_table['top'] = curve_table['mtm_pnl'].cummax()
            mtm_pnl = curve_table.iloc[-1]['mtm_pnl']
            curve_table['ddwn'] = curve_table['top'] - curve_table['mtm_pnl']
            max_equ = curve_table['mtm_pnl'].max()
            ddwns = curve_table[curve_table['ddwn'] > 0 ]
            max_dd, avg_dd, = ddwns['ddwn'].max(), ddwns['ddwn'].mean()

        return dict(tag=tag,mtm_pnl=mtm_pnl,max_equ=max_equ,max_dd=max_dd,avg_dd=avg_dd)



    def blend_curve(self,curve1,curve2,column):

        if curve1 is not None and not curve1.empty:
            ## setup index of the curve
            ## and copy mtm column to col=symbol_name
            
            if curve2 is not None and not curve2.empty:

                curve2 = curve2.set_index('timestamp')
                curve2['temp'] = curve2[column]

                ## concat columns by index
                ## and fill in NaN with prev value of each column
                curve1 = pandas.concat([curve1[column],curve2['temp']],join='outer',axis=1)
                curve1 = curve1.fillna(method='ffill')

                ## fill leading NaNs with zeros
                curve1 = curve1.fillna(value=0)

                #sum across columns
                #and replace tot mtm_pnl with the new value
                #curve1['new_pnl'] = curve1.sum(axis=1)
                #curve1['mtm_pnl'] = curve1['new_pnl']
                #curve1 = curve1[['mtm_pnl']]
                curve1 = pandas.DataFrame(curve1.sum(axis=1),columns=[column])
        else:

            if curve2 is not None and not curve2.empty:
                curve1 = curve2.copy()

        if curve1 is not None and 'timestamp' in curve1.columns:    
            curve1 = curve1.set_index('timestamp')

        return curve1


    def stats(self):

        ## reset the storage dictionary
        for k in self.storage.keys():
            self.storage[k] = dict()

        portfolio_stats = None
        ## portfolio_curve = None
        portfolio_curve_stats = None

        ## note: strat = portfolio_name holds all agg trade info
        for strat, activity in self.trading_activity.iteritems():
            comp_table = pandas.DataFrame()
            comp_stats = []
            activity_keys = activity.keys()
            activity_keys.sort()

            ## get the descriptive strategy_params for the strategy
            strategy_params = self.strategy_attributes.get(strat,{})
            if strategy_params:
                attr_table = pandas.DataFrame(strategy_params.items())
                attr_table.columns=['parameter','value']
                self.storage['settings'][strat] = attr_table 

            for sym in activity_keys:
                stat_table = pandas.DataFrame(activity[sym])
                stat_table['pnl_tot'] = stat_table['pnl'].cumsum()
                stat_table = stat_table[['symbol','qty','price','pnl','pnl_tot','owner','timestamp']]  ## rearrange columns
                self.storage['trades'][strat,sym] = stat_table

                #combine all symbols into a composite table
                comp_table = comp_table.append(stat_table,ignore_index=True)

                #calc pnl stats by symbol
                comp_stats.append(self.win_loss_stats(sym,stat_table))

            ## do overall calcs for strategy across all symbols
            blended_stats = self.win_loss_stats(strat,comp_table)
            comp_stats.append(blended_stats)

            comp_table = pandas.DataFrame(comp_stats)
            comp_table = comp_table[['tag','pnl','shrp','cnt','w_pct','w_avg','l_avg','w_std','l_std']]
            self.storage['trade_summary'][strat] = comp_table

            if strat == self.portfolio_name:
                portfolio_stats = blended_stats.copy()


        ##dump equ curves
        ##NOTE the composite curve is listed under strat=self.portfolio_name
        for strat, curves in self.equity_curves.iteritems():
            mtm = None
            realized = None
            comp_table = pandas.DataFrame()
            comp_stats = []
            curve_keys = curves.keys()
            curve_keys.sort()
            for sym in curve_keys:
                curve_df = pandas.DataFrame(curves[sym])

                ## trading equ entries take precedence
                ## so drop duplicate index entries where a pnl snap and mtm snap
                ## happen on the same timestamp
                ## DEPRECATED --> curve_df.drop_duplicates(subset=['timestamp'],take_last=True,inplace=True)
                curve_df.drop_duplicates(subset=['timestamp'],keep='last',inplace=True)
                curve_df.reset_index(inplace=True)
                curve_table = curve_df[['timestamp', 'symbol','qty','mtm','realized_pnl','mtm_pnl','owner']]
                self.storage['curve'][strat,sym] = curve_table

                ## calc equ_curve stats for that symbol
                comp_stats.append(self.equ_curve_stats(sym,curve_df))

                ## add in curve of each symbol per strategy
                strand = curve_df[['timestamp','mtm_pnl']]
                mtm = self.blend_curve(mtm,strand,'mtm_pnl')

                strand = curve_df[['timestamp','realized_pnl']]
                realized = self.blend_curve(realized,strand,'realized_pnl')

            ## start with blank curve data
            ## only blend curves that have data
            stat_curve = pandas.DataFrame() 
            blended_curve = None 
            if realized is not None:
                blended_curve =  pandas.concat([realized['realized_pnl'],mtm['mtm_pnl']],join='outer',axis=1)
                stat_curve = blended_curve[['mtm_pnl']]

            ##do overall stats of strategy's blended curve
            overall_stats = self.equ_curve_stats(strat,stat_curve)
            comp_stats.append(overall_stats)

            if strat == self.portfolio_name:
                portfolio_curve_stats = overall_stats

            comp_table = pandas.DataFrame(comp_stats)
            comp_table = comp_table[['tag','max_equ','max_dd','avg_dd']]
            self.storage['curve_stats'][strat] = comp_table 

            ## truncate blended curve if one has been created
            ## otherwise push a blank blended curve          
            curve_table = pandas.DataFrame([dict(timestamp=datetime.datetime(1900,1,1),realized_pnl=0,mtm_pnl=0)])
            if blended_curve is not None:
                blended_curve = blended_curve.reset_index()
                curve_table = blended_curve[['timestamp', 'realized_pnl', 'mtm_pnl']]
            self.storage['curve'][strat] = curve_table


        ## blend dictionaries
        portfolio_stats.update(portfolio_curve_stats)

        return portfolio_stats


    def write(self,filename=None):
        ## write all the stats to a pickle file
        ## for use by any other objects (i.e. StrategyView class, etc)
        
        if not self.storage['trades'].keys():
            self.stats()

        ## NOTE: if cPickle has trouble with the dict() of DataFrames
        ## try using the 'dill' module.
        
        if filename:
            root = ".".join(filename.split('.')[:-1])
            filename = "".join([root,'.pkl'])
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = "%s.%s.pkl" % (self.name,timestamp)

        try:
            self.log.info('writing pickle file: %s' % filename)    
            with open(filename, 'wb') as pickle_file:
                cPickle.dump(self.storage,pickle_file)
        except Exception as e:
            self.log.error('Unable to write pickle file: %s' % filename)
            self.log.error(type(e))


    def to_excel(self,filename=None):
        s = StorageToExcel(self.storage)

        if not filename:
            filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log.debug('writing to excel: %s' % filename)
        if not s.to_excel(filename):
            self.log.error('failed to write to excel: %s' % filename)


    ## kills the thread
    def shutdown(self):
        self.log.info('Portfolio Thread Stopped.')
        self.running = False

    def run(self):

        while self.running:

            with self.lock:

                ### get all new strategy orders
                ### published by each strategy
                for strat in self.STRAT_orders.keys():
                    try:
                        order = self.STRAT_orders[strat].get()
                        self.order_lookup[order.order_id] = order
                        self.log.info("registered order: %s" % order)
                    except IndexError:
                        pass

                ### recv fills and orders published by strategy
                ### record orders and collect fills and update aggregate positions
                try:
                    fill = self.IN_fills.peek()
                    if fill.timestamp <= self.current_timestamp:
                        fill = self.IN_fills.get()
                        order = self.order_lookup[fill.order_id]
                        ## update indv strat positions 
                        self.update_positions(fill.symbol,fill,order.owner)
                except IndexError:
                    pass


    def on_data(self,market_data):

        if market_data:

            self.current_timestamp = market_data.timestamp
            self.current_data[market_data.symbol] = market_data

            with self.lock:
                self.log.info("LIVE_DATA: %s" % market_data)

                ## collect most recent orders
                for strat in self.STRAT_orders.keys():
                    orders = self.STRAT_orders[strat]
                    while orders:
                        order = orders.get()
                        self.order_lookup[order.order_id] = order
                        self.log.info("registered order: %s" % order)

                ## deplete fill queue first
                while self.IN_fills:
                    
                    fill = self.IN_fills.peek()
                    if fill.timestamp <= self.current_timestamp:
                        fill = self.IN_fills.get()
                        order = self.order_lookup[fill.order_id]
                        ## update indv strat positions 
                        self.update_positions(fill.symbol,fill,order.owner)
                    else:
                        # no fills ready to process
                        break

                self.mark_to_market(market_data)
                  
                self.latch.notify()


    def on_data_sim(self,market_data):

        if market_data:

            self.current_timestamp = market_data.timestamp
            self.current_data[market_data.symbol] = market_data

            self.log.info("SIM_DATA: %s" % market_data)

            ## collect most recent orders
            for strat in self.STRAT_orders.keys():
                orders = self.STRAT_orders[strat]
                while orders:
                    order = orders.get()
                    self.order_lookup[order.order_id] = order
                    self.log.info("registered order: %s" % order)

            ## deplete fill queue first
            while self.IN_fills:
                
                fill = self.IN_fills.peek()
                if fill.timestamp <= self.current_timestamp:
                    fill = self.IN_fills.get()
                    order = self.order_lookup[fill.order_id]
                    ## update indv strat positions 
                    self.update_positions(fill.symbol,fill,order.owner)
                else:
                    # no fills ready to process
                    break

            self.mark_to_market(market_data)
              
            self.latch.notify()


    def on_EOD(self):

        self.log.info("reset on EOD")
        with self.lock:

            ## make sure the strategy queues are empty
            for order_queue in self.STRAT_orders.values():
                order_queue.clear()

            ## 2. push fills and do MTM
            while self.IN_fills:
                fill = self.IN_fills.peek()
                if fill.timestamp <= self.current_timestamp:
                    fill = self.IN_fills.get()
                    order = self.order_lookup[fill.order_id]
                    self.log.info("EOD fill: %s" % fill)
                    ## update indv strat positions 
                    self.update_positions(fill.symbol,fill,order.owner)
                else:
                    # no fills ready to process
                    # so get rid of any lingering fills
                    if self.IN_fills:
                        self.log.error('clearing portfolio of incomplete fills!')
                        self.IN_fills.clear()
                    break

            ## 3. send 'fake fills' to flatten out all positions
            self.create_fills_EOD()


    def create_fills_EOD(self):

        for strategy, positions in self.strategy_positions.iteritems():

            ## ignore the global portfolio positions
            if strategy == 'portfolio':
                continue

            for symbol in positions.keys():
                price_data = self.current_data[symbol]
                eod = positions[symbol]

                ## get current position and send a closing fill
                side = Order.SELL
                if eod.qty < 0: side = Order.BUY 
                fill = Fill(symbol,price_data.close,abs(eod.qty),side,price_data.timestamp,-1)
                self.log.info("SIMULATED EOD fill: %s" % fill)
                self.update_positions(fill.symbol,fill,strategy)



class StorageToExcel(object):

    def __init__(self,storage_dict):
        self.storage = storage_dict

    def to_excel(self,filename=None):
        ## write the storage dict file to xls
        
        root = ".".join(filename.split('.')[:-1])
        if not root: root = filename
        filename = "".join([root,'.xls'])
        excel_writer = pandas.ExcelWriter(filename)

        success = True

        try:
            print "writing excel file: %s" % filename
            with excel_writer as writer:

                ## composite strategy info
                for strat in self.storage['trade_summary'].keys():
                    try:
                        attr_table = self.storage['settings'][strat]
                        attr_table.to_excel(writer, 'SETTINGS %s' % strat)
                    except KeyError:
                        pass

                    trade_summary = self.storage['trade_summary'][strat]
                    trade_summary.to_excel(writer,'SUMMARY %s' % strat)

                    ## all curves summary info
                    curve_stats = self.storage['curve_stats'][strat]
                    curve_stats.to_excel(writer,'CURVE STATS %s' % strat)

                    curve_table = self.storage['curve'][strat]
                    curve_table.to_excel(writer,'CURVE %s' % strat)

                ## curves and trade information by symbol
                for strat_tuple in self.storage['trades'].keys():
                    #undo tuple
                    strat, sym = strat_tuple

                    ## trades per strategy, sym
                    stat_table = self.storage['trades'][strat, sym]
                    stat_table.to_excel(writer,'TRADES %s %s' % (strat,sym))

                    ## curve per symbol
                    curve_table = self.storage['curve'][strat, sym]
                    curve_table.to_excel(writer, 'CURVE %s %s' % (strat,sym))
        except Exception as e:
            print "Unable to write output Excel file: %s" % filename
            print e
            success = False

        return success



