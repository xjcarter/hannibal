
from MarketObjects import IndicatorMap

'''
testing the build of a dynamic indicator map
indicator map allows for independent indicators fro indiviudal symbols
allows a strategy to trade multiple symbols at the same time
'''

indicators = []

## indicator key_name, classname, parameters needed to define the indicator
indicators.append(('momentum','MO',{'length':10}))
indicators.append(('sma','SMA',{'length':20}))

indicator_map = IndicatorMap(indicators)

overrides = [ ('SPY','momentum',{'length':20}), ('IVV','momentum',{'length':5})]

indicator_map.override(overrides)

momentum_a = indicator_map['AAPL']['momentum']
momentum_b = indicator_map['SPY']['momentum']
momentum_c = indicator_map['IVV']['momentum']
sma_c = indicator_map['IVV']['sma']

print 'AAPL', momentum_a.length
print 'SPY', momentum_b.length
print 'IVV', momentum_c.length

for i in range(100):
	momentum_a.push(i)
	sma_c.push(i)

print momentum_a[0]
print sma_c[0]