
import random
import math
import string
import collections
import pandas
from prettytable import PrettyTable
import logging
import pprint
import sys
import datetime

from Simulator import Simulator
from Simulator import fitness_function

'''
	Optimizer of strategy
	using a genetic algorithm to find best parameters

	optimizer = Optimizer()
    optimizer.strategy_class = RetraceStrategy
   # optimizer.data_feed = DataFeedDaily('daily.SPY.csv')
    optimizer.data_feed = DataFeedDaily('SPY.csv')

    ## set population size
    optimizer.size = 40 
    optimizer.max_generations = 50
    optimizer.outfile = 'optimize_retrace.xls'

    ## resets all trading activity when file reaches end.
    optimizer.reset_on_EOD = True

    ## parameter space to search over
    ## strategy_params for RetraceStrategy = dict(average,momentum,duration)
    ## momentum = entry momentum crossover
    ## average = moving average filter
    ## duration = trade holding period
     
    param_list = [dict(name='momentum',min_val=10,max_val=100,steps=32,converter=int),
                  dict(name='average',min_val=20,max_val=200,steps=32,converter=int),
                  dict(name='duration',min_val=10,max_val=50,steps=16,converter=int) ]

    for p in param_list:
        optimizer.add_parameter(p)

    optimizer.run()

'''


# turn off all logging outside optimizer 
# set level = CRITICAL for the general config does this
logging.basicConfig(level=logging.CRITICAL,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='optimizer.log')
                    ## filemode='w')

# set the optimizer logger to DEBUG
# and additionally dump optimizer output to the console
# 'Optimizer' logger tag is defined in the Optimizer module
log = logging.getLogger('Optimizer')
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)

sim_log = logging.getLogger('Simulator')
sim_log.setLevel(logging.CRITICAL)


'''
Genetic Algorithm optimization engine
'''


# Generate r randomly chosen, sorted integers from [0,n)
def _sample(n, r):
    pop = n
    for samp in xrange(r, 0, -1):
        cumprob = 1.0
        x = random.random()
        while x < cumprob:
            cumprob -= cumprob * samp / pop
            pop -= 1
        yield n-pop-1


# utility to reshape a dictionary in specific order
def _order_dict(dct,order_list):
	x = collections.OrderedDict([(k,dct[k]) for k in order_list if k in dct])
	remainders = list(set(dct.keys()) - set(order_list))
	remainders.sort()
	for k in remainders:
		x[k] = dct[k]

	return x


'''
Segment defines a single 'gene'.
steps = the number of values to be generated between min_val, max_val
converter = function that 'formats' the generated test values (default = float)
constant values are created by setting min_val = max_val
'''


class Segment(object):
	def __init__(self, name,min_val,max_val,steps=8,converter=float):
		self.name = name
		self.min_val = min_val
		self.max_val = max(max_val,min_val)
		self.steps = 0
		self.step_size = 0
		self.width = 0 
		if self.min_val < self.max_val:
			self.steps = int(steps)
			self.step_size = (max_val - min_val)/float(steps-1)
			self.width = int(math.log(steps,2))

		self.value = None

		self.bits = {}

		if self.steps == 0:
			## map a single constant value
			self.bits['0'] = self.min_val
		else: 
			## build out complete bitstring-value map
			i = 0
			v = self.min_val
			while True:	
				v = min(self.max_val,self.min_val + i * self.step_size)
				b = bin(i)[2:].zfill(self.width)
				self.bits[b] = converter(v)
				if v >= self.max_val: break
				i += 1

	def gen_value(self):
		if self.steps == 0:
			self.value = '0'
		else:
			self.value = random.choice(self.bits.keys())
		return self.value

	def decode(self,bit_key):
		try:
			return self.bits[bit_key]
		except:
			return None

	def __repr__(self):
		return '--- %s\n%s' % (self.name,pprint.pformat(self.bits))

'''
StrandFactory creates Strands from a list of Segments
a Strand represents a completely encoded sequence of model parameters
'''

class StrandFactory(object):
	def __init__(self,segments=[]):
		self.segments = []
		self.length = 0
		self.capacity = 0
		self.count = 0 
		self.registry = {}
		self.strand_pool = []

		## holds list of segments that are fixed values
		## i.e. min_val = max_val, steps = 0 
		self.constants = []
		self.consts = 0

		for seg in segments:	
			self.add(seg)

		self.add_lock = False

	def add(self,segment):

		## lock function once one value is generated
		## see gen_value()
		
		if self.add_lock:
			log.warning('add function locked. strand length fixed at %d' % self.length)
			return

		if segment.steps > 0:
			## add segment that has a parameter range
			if self.segments:
				## always
				self.segments.append((segment,segment.width + self.length))
			else:
				self.segments.append((segment,segment.width))
		else:
			## add to constant values
			self.constants.append(segment)

		self.consts = len(self.constants)
		if self.segments:
			self.length = self.segments[-1][-1]
			self.capacity = 2**self.length 


	def exhausted(self):
		return self.count >= self.capacity

	def __repr__(self):
		return pprint.pformat(self.segments)


	def _get_value(self):

		## generate complete search space for bit length < 10
		## this will decrease the hashing collisions in the registry
		if self.length < 10 and not self.strand_pool:
			self.strand_pool = [ bin(x)[2:].zfill(self.length) for x in xrange(self.capacity) ]
			random.shuffle(self.strand_pool)

		if self.strand_pool:
			return self.strand_pool.pop()
		else:
			return "".join([ s[0].gen_value() for s in self.segments ])

	## if the factory contains Segments with constant values
	## prepend '0's fro each constant Segment
	def _prepend_constants(self,value):
		v = value
		if self.consts > 0:
			head = '0' * self.consts
			v = "".join([head,value])
		return v


	def gen_value(self):

		## once the first value is generated -
		## freeze the strand factory length
		if not self.add_lock:
			self.add_lock = True

		tries = 0
		while tries < 1000 and self.count < self.capacity:
			value  = self._prepend_constants(self._get_value()) 
			try:
				v = self.registry[value]
				tries += 1
				log.debug('\tgen_value miss (%d): %s' % (tries,value))
			except KeyError:
				self.registry[value] = self.count
				self.count += 1
				return value

		log.info('Unable to generate new strands - gen_value() limit (%d) hit' % self.count)


	def register_value(self, value):
		## takes a generated value and makes sure it is unique
		## otherwise grabs a new values
		try:
			v = self.registry[value]
			log.debug('value collision: %s' % value)
		except KeyError:
			self.registry[value] = self.count
			self.count += 1
			return value 
		else:
			return self.gen_value()



	def decode(self,strand):

		## constants are a the head of a strand
		## marked by '0's
		if self.constants:
			strand = strand[self.consts:]

		decode_dict = collections.OrderedDict()
		p =0
		for s in self.segments:
			segment, end_point = s
			v = strand[p:end_point]
			decode_dict[segment.name] = segment.decode(v)
			p = end_point

		for c in self.constants:
			decode_dict[c.name] = c.decode('0')

		return dict(decode_dict)



	def cross(self, strand1, strand2):
		## IMPORTANT NOTE: this assumes len(strand1) = len(strand2) = self.length
		
		## to speed up population generation
		## it tries to find original offspring first, then defaults to new immigrants
		
		s1 = s2 = None
		if self.length < 8:
			## don't cross - just randomly select new values
			s1 = self.gen_value()
			s2 = self.gen_value()
			return [s1, s2]


		a, b = _sample(self.length,2)

		if self.length < 16:
			## single point crossover
			s1 = "".join([strand1[:b],strand2[b:]])
			s2 = "".join([strand2[:b],strand1[b:]])
		## strand length > 16	
		else:
			## two point crossover
			s1 = "".join([strand1[:a],strand2[a:b],strand1[b:]])
			s2 = "".join([strand2[:a],strand1[a:b],strand2[b:]])

		s1 = self.register_value(s1)
		s2 = self.register_value(s2)

		return [s1, s2]



	def flip_bit(self,strand,bit_index):
		v = list(strand)
		if bit_index < self.length:
			a = v[bit_index]
			if a == '1':
				v[bit_index] = '0'
			else:
				v[bit_index] = '1'

		return "".join(v)




''' 
Genetic Algorithm optimizing engine
'''


class Optimizer(object):

	def __init__(self):

		self.population = []
		self.results_map = {}
		self.index = 0 

		## make sure these are both even numbers
		self.size = 24 
		self.cutoff = 12 
		self.pairs_needed = (self.size - self.cutoff)/2

		self.generation = 0
		self.max_generations = 100
		self.tolerance = 0.10
		self.min_trade_count = 30 

		## flags Simulator to do EOD calls
		self.reset_on_EOD = True

		self.optimizer_df = pandas.DataFrame()
		self.run_map = {} 

		self.factory = StrandFactory()

		## handles for the derived StrategyBase class and its constructor parameters
		## strategy_setup = dict(), 
		## NOTE!!! strategy_params will be generated by optimizer
		
		self.strategy_class = None
		self.strategy_setup =None	

		## handle for the DataFeed object to be used in optimization
		self.data_feed = None

		## turn on Simulator verbosity
		self.verbose = False

		## output controls
		self.display_dump = True
		## filename to write output to
		self.outfile = None


	def add_parameter(self,parameter):
		## parameter = dict(name, min_val, max_val, steps, converter)
		self.factory.add(Segment(**parameter))

	def add_parameters(self,parameter_list):
		## parameter = dict(name, min_val, max_val, steps, converter)
		if isinstance(parameter_list,list):
			for parameter in parameter_list:
				self.factory.add(Segment(**parameter))
		else:
			log.error('Optimizer.add_parameters takes a list.')


	def get_pairs(self):
		### grab pairs via tournament selection
	    originals = {}
	    pairs = []
	    cnt = 0
	    pair_count = 0
	    while pair_count < self.pairs_needed:
	        a, b = list(_sample(self.cutoff,2))
	        c, d = list(_sample(self.cutoff,2))
	        pair = (a,c)
	        if a == c: pair = (a,min(b,d))
	        try:
	            x = originals[pair]
	        except KeyError:
	        	originals[pair] = True
	    		pairs.append(pair)
	    		pair_count += 1

        	assert cnt < 100, "pairs generation not converging"
	        cnt += 1

	    #for p in pairs: print p

	    return pairs


	def converged(self):
		## self.population = [] of
		## [fitness_score, strand_bit_string] elements
	
		if not self.population:
			return False

		if self.generation >= self.max_generations:
			log.info("maximum generations reached")
			return True

		if self.factory.exhausted():
			log.info("search space exhausted")
			return True

		self.population.sort(reverse=True)

		## get difference in ordered scores
		diff = self.population[0][0] - self.population[self.cutoff-1][0]

		if abs(diff) <= self.tolerance * self.cutoff:
			log.info("convergence tolerance hit")
			return True

		return False


	def score(self,score_input,run_id):
		fitness_score = fitness_function(score_input, min_trades=self.min_trade_count)

		## self.population = [] of
		## [fitness_score, strand_bit_string] elements
		self.population[self.index][0] = fitness_score
		bitcode = self.population[self.index][1]

		if self.results_map.get(bitcode,None):
			params = self.factory.decode(bitcode)
			old_id = self.results_map[bitcode][1]
			err_items = (run_id,old_id,bitcode,params)
			log.error('run_id = %d, old_id = %d: bitcode: %s, params: %s ALREADY SCORED.' % err_items)

		self.results_map[bitcode] = (score_input, run_id)

		##increment pointer into the population
		self.index += 1

	## record and display output for the most recent 
	## optimization run
	def dump(self,display=True):
		self.population.sort(reverse=True)
		output = []
		for score, bitcode in self.population:
			stats, run_id = self.results_map[bitcode]
			params = self.factory.decode(bitcode)
			output.append((score,stats,params,run_id))
			self.run_map[run_id] = params

		stats_table, df = self._table(output)

		## concat new output
		self.optimizer_df = pandas.concat([self.optimizer_df,df])

		if display:
			log.info('\n%s' % stats_table)

		## persists the last generation	
		self.write()

	## return and show optimizer params for a given run_id
	def __getitem__(self,index):
		params = self.run_map[index]
		p = PrettyTable(params.keys())
		p.add_row(params.values())
		print 'run_id = %d' % index
		print p

		return params

	## write output to file
	def write(self):

		filename = self.outfile
		if not filename:
			if self.strategy_class:
				filename = self.strategy_class.__name__
			else:
				filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

		try:
			root = ".".join(filename.split('.')[:-1])
			if not root: root = filename
			filename = "".join(["opz_",root,'.xls'])
			excel_writer = pandas.ExcelWriter(filename)
			sorted_df = self.optimizer_df.sort_values(by=['gen_id','score'],ascending=False)
			sorted_df['strategy'] = self.strategy_class.__name__
			log.info("Writing output file: %s" % filename)
			with excel_writer as writer:
				sorted_df.to_excel(writer,'OPTIMIZER',filename)
		except Exception as e:
			log.error("Unable to write output file: '%s' for optimizer" % filename)
			log.error(str(e))


	def _table(self,output):

		table_data = []
		header = None
		df_header = None
		stats_table = None
		for row, item in enumerate(output):
			score, stats, params, run_id = item

			params = _order_dict(params,[])
			stats = _order_dict(stats,['cnt','w_pct','pr','pnl','mtm_pnl','max_equ','max_dd'])

			## override the tag field to list row number
			row += 1
			marker = str(row)
			if row == self.cutoff: marker = '*%d' % row
			stats['tag'] = marker
			
			if not header:
				header = ['gen_id', 'run_id', 'score']
				header.extend(stats.keys())
				df_header = header[:]
				## separate stats from parameters by and empty column
				df_header.append("  ")		
				df_header.extend(params.keys())

				stats_table = PrettyTable(header)
				for col in stats.keys():
					if col not in ['tag','cnt']:
						stats_table.float_format[col] = '0.2'
				stats_table.float_format['score'] = '0.2'

			s_items = [self.generation,run_id,score]
			s_items.extend(stats.values())
			stats_table.add_row(s_items)

			items = s_items[:]
			items.append("  ")
			items.extend(params.values())
			table_data.append(dict(zip(df_header,items)))

		df = pandas.DataFrame(table_data)
		df = df[df_header]

		## just show an abbrievated version of stats_table
		## keep the full table around just in case needed
		
		abbrv = ['gen_id','run_id','score','cnt','pnl','pr','mtm_pnl','max_equ','max_dd','w_pct','tag']
		stats_table = stats_table.get_string(fields=abbrv)
		
		return stats_table, df


	def generate_set(self):

		## population to be converted to parameter sets
		new_pop = []

		## self.population = [] of
		## [fitness_score, strand_bit_string] elements

		if len(self.population) == 0:
			i = 0
			## generate fresh population with score = 0 
			while i < self.size:
				v = self.factory.gen_value()
				if not v:
					break
				new_pop.append(v)
				## init score = 0
				self.population.append([0,v])
				i += 1

			## all new elements -
			## therefore start at the top of the population array
			self.index = 0
		else:
			self.population.sort(reverse=True)
			## grab the elites and drop scores below cutoff
			self.population = self.population[:self.cutoff]
			p = self.population[:]

			## mate pairs and give them score = 0 
			pairs = self.get_pairs()
			## log.debug("pairs = %s" % pprint.pformat(pairs))
			while len(pairs) > 0:
				pair = pairs.pop()
				x, y = pair

				## grab the bitcode within the population
				## indexed by the pair values generated
				strand1, strand2 = p[x][1], p[y][1]

				## log.debug("crossing %d (%s), %d (%s)" % (x,strand1,y,strand2))
				new_strands = self.factory.cross(strand1,strand2)

				if new_strands:
					new_pop.extend(new_strands)
					## tag newly generated strands with score = 0
					## then add them to the population array
					self.population.extend([ [0,s] for s in new_strands ])
				else:
					## search pool is exchausted
					break

			## fill in the rest of the population with fresh new strands
			if len(self.population) < self.size:
				j = len(self.population)
				## generate fresh population with score = 0 
				while j < self.size:
					v = self.factory.gen_value()
					if not v:
						break
					new_pop.append(v)
					## init score = 0
					self.population.append([0,v])
					j += 1



			## reset the index pointer into the population
			## new elements start beyond the cutoff
			self.index = self.cutoff

		## decode new parameter set
		new_parameters = []
		for v in new_pop:
			new_parameters.append(self.factory.decode(v))

		self.generation += 1

		return new_parameters


	'''
	Optimizer Execution Loop Functions
	'''

	## creates a random string with a uniqueness > max search size
	## this allows us to uniquely identify simulation runs within optimizer
	## -- even over multiple optimization runs that log to the same log file.
	
	def _tempname(self):
		name_length = int(math.log(self.factory.capacity,26)+2)
		return "".join([random.choice(string.ascii_uppercase) for i in range(name_length)])


	def run(self):

	    run_id = 0
	    while not self.converged():
			params_set = self.generate_set()
			for strategy_params in params_set:
				log.info('run_id = %d: %s' % (run_id,pprint.pformat(strategy_params)))
				name = '%s_%s' % (self.strategy_class.__name__, self._tempname())
				s = Simulator()
				s.reset_on_EOD = self.reset_on_EOD
				## if you want have unique portfolio names per optimizer run
				## s.portfolio.name = "".join(['portfolio_',name])
				s.verbose = self.verbose 
				s.add_strategy(self.strategy_class(name,strategy_setup=self.strategy_setup,strategy_params=strategy_params))
				self.data_feed.reset()
				summary = s.run(self.data_feed)
				self.score(summary,run_id)
				run_id += 1
			self.dump(display=self.display_dump)




		






