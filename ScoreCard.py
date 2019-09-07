
import pandas

'''
ScoreCard is ne object that does all automated 'scorekeeping' for a trading campaign
  - it takes a trading blotter DataFrame as input, 
    - take in a blotter with required columns = [date,symbol,amount, price, t_cost]
  - and a needs a data_source directory to do mark-to-market calculations
  
self.data_path = directory holding datafiles for symbols daily data (like SPY.daily.csv)
self.outfile = output file of the scorecard, provides pnl curves by symbol and win/loss, profit_ratio stats
self.curves = dict of pnl curve dataframes indexed by symbol

usage:
c = ScoreCard()
c.score_blotter(blotter_df)

'''

class ScoreCard(object):

	def __init__(self):
		self.data_path = "."
		self.outfile = 'scorecard.xls'
		self.curves = dict()

	def pnl_stats(self,pnl):

		wins = [x for x in pnl if x > 0]
		losses = [x for x in pnl if x <= 0 ]
		win_pct = 0
		if wins and pnl:
			win_pct = float(len(wins))/len(pnl)

		profit_ratio = 0
		if wins and losses:
			mwin = float(sum(wins))/len(wins)
			mloss = float(sum(losses))/len(losses)
			profit_ratio = 0
			if mloss != 0:
				profit_ratio = mwin/abs(mloss)

		return win_pct, profit_ratio


	def trade_update(self,trd,t_price,pos,a_price):
		trade_pnl = 0
		closed = False
		n_price = a_price
		if trd * pos <= 0:
		    a_pos, a_trd = abs(pos), abs(trd)
		    trade_pnl = min(a_pos,a_trd) * (t_price - a_price)
		    ## closing a short
		    if trd > 0: trade_pnl = -trade_pnl
		    ## new  net position gets trade price                 
		    if a_pos <= a_trd: n_price = t_price
		    closed = True
		else:
		    n_price = ((pos * a_price) + (trd*t_price))/(pos+trd)

		return pos+trd, n_price, trade_pnl, closed


    ## takes a blotter df = [date,symbol,amount,price]
   	## blotter from MockStrategy = [date, starting_capital, symbol, amouht, price, t_cost, ending_capital]
	def score_blotter(self,df):
		df = df.sort(['date'],ascending=True)
		trades = dict(list(df.groupby(['symbol'])))

		tot_curve = None
		tot_pnl = []
		stats = []

		excel_writer = pandas.ExcelWriter(self.outfile)
		with excel_writer as writer:
			for symbol, group in trades.iteritems():
				scorecard = []
				net_position = avg_price = 0
				pnl = []
				for i, row in group.iterrows():
				    net_position, avg_price, trade_pnl, closed = self.trade_update(row['trade'],row['price'],net_position,avg_price)
				    new_row = dict(row)
				    new_row.update(dict(net_position=net_position,avg_price=avg_price,trade_pnl=trade_pnl))
				    scorecard.append(new_row)
				    if closed:
						pnl.append(trade_pnl)

				tot_pnl.extend(pnl)

				win_pct, profit_ratio = self.pnl_stats(pnl)
				stats.append(dict(symbol=symbol,count=len(pnl),win_pct=win_pct,profit_ratio=profit_ratio))   	

				result = pandas.DataFrame(scorecard)
				result = self.bind_curve(symbol,result)
				self.curves[symbol] = result

				result.to_excel(writer,symbol)
				if 'tot_pnl' in result.columns:
					tot_curve = self.blend_curve(tot_curve,result,'tot_pnl')


			win_pct, profit_ratio = self.pnl_stats(tot_pnl)
			stats.append(dict(symbol='TOTAL',count=len(tot_pnl),win_pct=win_pct,profit_ratio=profit_ratio))
			stats_df = pandas.DataFrame(stats)
			stats_df = stats_df[['symbol','count','win_pct','profit_ratio']]

			stats_df.to_excel(writer,'PNL_STATS')
			tot_curve.to_excel(writer,'TOTAL')
			self.curves['TOTAL'] = tot_curve
		

	def bind_curve(self,symbol,df):
		df = df.reset_index()
		start_date = df.loc[0,'date']
		try:
			curve_file = "%s\\%s.daily.csv" % (self.data_path,symbol)
			curve = pandas.read_csv(curve_file)
			curve = curve.rename(columns={'symbol':'sym'})
			curve = curve.reset_index()
	 
			g = curve.merge(df,on='date',how='outer')

			g['trade'] = g['trade'].fillna('')
			g['price'] = g['price'].fillna('')
			g['net_position'] = g['net_position'].ffill()
			g['net_position'] = g['net_position'].fillna(0)
			g['avg_price'] = g['avg_price'].ffill()
			g['avg_price'] = g['avg_price'].fillna(0)
			g['trade_pnl'] = g['trade_pnl'].fillna(0)
			g['mark_pnl'] = g['net_position']*(g['close'] - g['avg_price'])
	 
			g['realized_pnl'] = g['trade_pnl'].cumsum()
			g['tot_pnl'] = g['mark_pnl'] + g['realized_pnl']

			g = g[g['date'] >= start_date]

			g = g[['date','symbol','trade','price','net_position','avg_price','close','trade_pnl','mark_pnl','realized_pnl','tot_pnl']]

			return g
		except Exception as e:
			print 'cannot bind curve for %s' % symbol
			print e
			return df


	def blend_curve(self,curve1,curve2,column):

		if curve1 is not None and not curve1.empty:
       		## setup index of the curve
       		## and copy mtm column to col=symbol_name
            
			if curve2 is not None and not curve2.empty:

				curve2 = curve2.set_index('date')
				curve2['temp'] = curve2[column]

				## concat columns by index
				## and fill in NaN with prev value of each column
				curve1 = pandas.concat([curve1[column],curve2['temp']],join='outer',axis=1)
				curve1 = curve1.fillna(method='ffill')

				## fill leading NaNs with zeros
				curve1 = curve1.fillna(value=0)

				#sum across columns
				curve1 = pandas.DataFrame(curve1.sum(axis=1),columns=[column])
		else:
			if curve2 is not None and not curve2.empty:
				curve1 = curve2.copy()

		if curve1 is not None and 'date' in curve1.columns:    
		    curve1 = curve1.set_index('date')

		return curve1

