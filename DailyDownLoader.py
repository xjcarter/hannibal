
import pandas
import pandas.io.data
from glob import glob
import os.path
from os import sep
from datetime import datetime, timedelta
from MarketObjects import parse_date

'''
DailyDownLoader 

Daily update class for daily stock data. (sourced from yahoo)
The class takes a path of the directory where the data updates are to take place
The class looks in the directory for files of the <SYMBOL>.daily.csv file signature
and look to update the files data to the current date.
Additionally, if there is a _universe_.csv file in the directory, the class will
use the contents of the symbol listing file (.csv file that lists the symbols desired)
to download new or update symbols given.

add_symbols() lets you add a list of symbols to download interactively.
update_data() does the downloading
'''

class DailyDownLoader(object):
	
	current_dir = "." + sep

	def __init__(self,path=current_dir):
		self.path = path
		self.default_start = datetime(2005,1,1) 

		self.universe = dict()
		fn_universe = self.path + '_universe_.csv'
		if os.path.exists(fn_universe):
			f = open(fn_universe,'rb')
			for line in f.readlines():
				if 'ymbol' in line:
					## ignore header
					continue
				else:
					symbol = line[:-2].split(',')[0]
					filename = '%s%s.daily.csv' % (self.path, symbol)
					self.universe[symbol] = filename

		fn_regex = '%s*.daily.csv' % self.path
		for filename in glob(fn_regex):
			symbol = os.path.basename(filename).split('.')[0]
			self.universe[symbol] = filename

	## allows you to request a list of symbols 
	## without setting up a _universe_.csv file
	def add_symbols(self,symbol_list):
		for symbol in symbol_list:
			filename = '%s%s.daily.csv' % (self.path, symbol)
			self.universe[symbol] = filename

	def update_data(self):

		for symbol, filename in self.universe.iteritems():
			if os.path.exists(filename):
				df = pandas.read_csv(filename)
				last_date = df.loc[df.index[len(df)-1],'date']
				next_date = datetime.strptime(last_date,'%Y-%m-%d')
				next_date += timedelta(days=1)
				self._fetch_data(symbol,next_date,filename,df)
			else:
				self._fetch_data(symbol,self.default_start,filename)

	def _format_date(self,date_string):
		dt = parse_date(date_string)
		return dt.strftime("%Y-%m-%d")

	## Note for simulation testing its best to use adjusted
	## close - but when running mock strategies versus a live 
	## blotter need to compare closes to closes...
	def _fetch_data(self,symbol,date,filename,current_df=None):

		if date > datetime.now():
			print "symbol: %s up to date." % symbol
			return

		try:
			df = pandas.io.data.DataReader(symbol, "yahoo", start=date.strftime("%Y-%m-%d"))
			if not df.empty:
				df.index.names = ['date']
				df.columns = [x.lower() for x in df.columns.tolist()]
				df.drop(['close'],axis=1,inplace=True)
				##df.drop(df.index[-1],inplace=True)
				df.rename(columns={'adj close': 'close'},inplace=True)
				df['symbol'] = symbol
				df = df[['open','high','low','close','volume','symbol']]

				## change the date index to a string
				df = df.reset_index()
				df['date'] = df['date'].map(lambda x:x.strftime("%Y-%m-%d"))
				df = df.set_index('date')

				if isinstance(current_df,pandas.core.frame.DataFrame):
					if not current_df.empty:
						current_df['date'] = current_df['date'].map(self._format_date)
						current_df = current_df.set_index('date')
						df = pandas.concat([current_df,df])

				df.to_csv(filename)

		except Exception as e:
			print 'unable to process symbol: %s  filename: %s' % (symbol, filename)
			print e

