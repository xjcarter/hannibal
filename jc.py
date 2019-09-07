
import pandas
import tempfile
import os
import sys, traceback
import clr
import System
import linecache
from pprint import pprint
 
## helper util file for doing stuff in native python / ipdb
 
## open DataFrame in Excel window
def dump(df,filename=None):
    """
        Opens file in the default windows program
    """
    tmp_name = None
    if filename:
        f=tempfile.NamedTemporaryFile(delete=False, dir='M:\\sandbox\\tmp', suffix='.csv', prefix='%s__' % filename)
        tmp_name=f.name
        f.close()
    else:
        f=tempfile.NamedTemporaryFile(delete=False, dir='M:\\sandbox\\tmp', suffix='.csv', prefix='tmp_')
        tmp_name=f.name
        f.close()
 
    df.to_csv(tmp_name)
 
    if os.path.isfile(tmp_name):
        System.Diagnostics.Process.Start(tmp_name)
 
from pandas.sandbox.qtpandas import DataFrameWidget
from PySide import QtGui
 
## open DataFrame in DataFrameWidget Window
def to_qt(in_df):
    """
    uses pyside to display dataframe within QtWidget
    Arguments:
    in_df: Input data frame
    """
    if QtGui.QApplication.instance() is not None:
        app = QtGui.QApplication.instance()
    else:
        app = QtGui.QApplication(sys.argv)
    widg = DataFrameWidget(in_df)
    widg.show()
    app.exec_()
 
##df = pandas.DataFrame([{'a':2, 'b':3}, {'a':5, 'b':7}])
## to_qt(df)
##open_df(df)
 
## print out first level of stack trace
def print_exception():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)
 
def print_stack_trace(verbose=False):
    """
    Print the usual traceback information, followed by a listing of
    all the local variables in each frame.
    """
    tb = sys.exc_info()[2]
    while tb.tb_next:
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    stack.reverse()
    traceback.print_exc()
    print "Locals by frame, innermost last"
    for i, frame in enumerate(stack):
        if verbose:
            print
        else:
            print "  " * i,
        print "Frame %s in %s at line %s" % (frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno)
        if verbose:
            for key, value in frame.f_locals.items():
                print "\t%30s = " % key,
                # we must _absolutely_ avoid propagating exceptions, and str(value)
                # COULD cause any exception, so we MUST catch any...:
                try:
                    if isinstance(value, pandas.DataFrame):
                        tmpfilename ="%s___%s" % (key.upper(),frame.f_code.co_name)
                        dump(value,tmpfilename)
                        print "DataFrame <%s>" % tmpfilename
                    else:
                        pprint(value)
                except:
                    print "<ERROR WHILE PRINTING VALUE>"
 
