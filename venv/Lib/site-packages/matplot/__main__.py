# -*- coding: utf-8 -*-
#main entry for pyloco command-line interface
from .matplot import MatPlot as entry_task
from pyloco.main import perform


if __name__ == "__main__":
    import sys
    import multiprocessing
    multiprocessing.freeze_support()

    if "--" in sys.argv:
        idx = sys.argv.index("--")
        perform(entry_task, sys.argv[1:idx], sys.argv[idx+1:])
    else:
        perform(entry_task, sys.argv[1:])
