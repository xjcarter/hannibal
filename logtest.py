
import logging
from Optimizer import Segment
from prettytable import PrettyTable
import sys

# set up logging to file - see previous section for more details
logging.basicConfig(level=logging.CRITICAL,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='test_logging.txt',
                    filemode='w')

log = logging.getLogger('default')
spam = logging.getLogger('test')
spam.setLevel(logging.DEBUG)

fh = logging.FileHandler("spam.txt")
console = logging.StreamHandler(sys.stdout)

spam.addHandler(fh)
spam.addHandler(console)
log.debug('Hit this!')

s = Segment('test',10,30)
m = PrettyTable(['bitcode','value'])
for k,v in s.bits.iteritems(): m.add_row([k,v])
spam.debug(m)


