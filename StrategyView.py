
import pandas
import matplotlib.pylab as pylab
import seaborn
import cPickle
from Portfolio import StorageToExcel

## setup for better looking graphs
pandas.options.display.mpl_style = 'default'
pylab.rcParams['figure.figsize'] = 10, 8


'''
StrategyView is a simple object that takes a pickled file
of a Portfolio output - it allows to examine data output outside of Excel
'''

class StrategyView(object):
	def __init__(self,filename):

		self.filename = filename
		fh = open(filename,'rb') 
		self.storage = cPickle.load(fh) 
		fh.close()

	def index(self):
		## print the dictionary indicies
		categories = sorted(self.storage.keys())
		for k in categories:
			print k
			tags = sorted(self.storage[k].keys())
			for sk in tags:
				print "\t", sk
			print ""

	def table(self,index,tag,to_html=False):
		table = self.storage[index][tag]
		## 't' is a pandas DataFrame
		## may need to massage for Jupyter
		if not to_html: 
			return table
		else:
			## do html conversion here
			pass

	def plot_curve(self,tag):
		## only grabs curves and tries to plot them
		c = self.storage['curve'][tag]
		c.plot(x='timestamp')

	def plot_trades(self,tag,kind='bar'):
		c = self.storage['trades'][tag]
		trades = c['pnl']
		trades = trades[~pandas.isnull(trades)]
		if kind == 'hist':
			trades.plot(kind='hist',bins=30)
		else:
			trades.plot(kind='bar',color='gray')

	def to_excel(self, filename=None):
		if not filename: filename = self.filename
		s = StorageToExcel(self.storage)
		s.to_excel(filename) 
	
