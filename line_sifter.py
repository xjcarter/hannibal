
## line_sifter filename sample_num
## grabs every 'sample_num' line from a sequential data file

import sys
f = open(sys.argv[1],'rb')
j = int(sys.argv[2])
for i, line in enumerate(f.readlines()):
	line = line[:-2]
	if i == 0 or i % j == 0:
		print line

