# -*- coding: utf-8 -*-
"""main entry module."""

from __future__ import unicode_literals

import sys
import os
import pdb
import multiprocessing

from pyloco.manage import PylocoManager
from pyloco.grouptask import GroupCmdTask
from pyloco.stdtask import GroupInputCmdTask
from pyloco.mgmttask import mgmt_tasks
from pyloco.task import Task, OptionTask, load_taskclass
from pyloco.error import (TestError, InternalError, UsageError, NormalExit,
                          TypeCheckError)
from pyloco.util import pyloco_shlex


# TODO: supporing test task
#      - a task class may have methods fo testing like test_... or
#        pylocotest_ ...
#      - plx may has sections for testing like setup*, teardown*, test*, ....

# TODO: supporing register and install tasks
#      - pyloco test task task-options with acutual argument
#      - first test the task, generate input output pickles,
#        and make a package and register

# TODO: documentation
#   - context-aware doc with --doc option

# TODO: alias task

# TODO: .plw file for webapp
# TODO: .exe file for cliapp and guiapp

# TODO: command line syntax to support group :
#       pyloco -- ( sfds -- dsfsd -- fsds ) --argument --

# TODO: within multiproc, error makes error, not only logging

# TODO: --send "(1,2,3),x,y,z=x+y" MPI ISEND : a task of comm-comp overlap,
#      IRECV is implicit in waitall
# TODO: --wait "from=(1,2,3),avail=(x,y,z), ack=(1,2,3)" MPI WAITALL
# NOTE: Support of general graph of tasks???

# TODO: --pdb leads to pdb debugger if exceptions

# TODO: supports update command
# TODO: supports anaconda and jupyter notebook

def _excepthook(type, value, tb):
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)

    else:
        import traceback, pdb
        traceback.print_exception(type, value, tb)
        pdb.post_mortem(tb)

def _extract_option(opts, argv, subargv):

    out = []

    for opt in opts:
        if opt in argv or opt in subargv:
            argv[:] = [a for a in argv if a != opt]
            subargv[:] = [a for a in subargv if a != opt]
            out.append(True)
        else:
            out.append(False)

    return tuple(out)

def main(argv=None, manager=None):
    """run a task from command-line
        Handling pyloco options
    """

    if argv is None:
        argv = sys.argv[1:]
    elif isinstance(argv, str):
        argv = pyloco_shlex.split(argv)

    if manager is None:
        manager = PylocoManager

    if not argv:
        print("usage: " + manager._usage_.format(manager=manager._name_))
        print(manager._help_help_.format(manager=manager._name_))
        return 0

    num_pipes = argv.count("--")

    if num_pipes > 0:

        idx = argv.index("--")
        targv, sargv = argv[:idx], argv[idx+1:]

        if targv:
            if targv[0] == "input":
                ret, _ = perform(GroupInputCmdTask, argv=targv[1:],
                                 subargv=sargv, manager=manager)

            elif targv[0] in mgmt_tasks:
                ret, _ = perform(targv[0], argv=targv[1:], subargv=sargv,
                                 manager=manager)

            elif targv[0].startswith("-"):
                ret, _ = perform(GroupCmdTask, argv=targv, subargv=sargv,
                                 manager=manager)

            else:
                ret, _ = perform(GroupCmdTask, subargv=argv, manager=manager)
        else:
            ret, _ = perform(GroupCmdTask, subargv=sargv, manager=manager)

    elif argv[0].startswith("-"):
        ret, _ = perform(OptionTask, argv=argv, manager=manager)

    else:
        task = argv.pop(0)
        ret, _ = perform(task, argv=argv, manager=manager)

    return ret


def perform(task, argv=None, subargv=None, parent=None, forward=None,
            shared=None, return_directory=None, manager=None):

    multiprocessing.freeze_support()

    out = -1, None

    if forward is None:
        forward = {}

    if isinstance(argv, str):
        argv = pyloco_shlex.split(argv)

    elif argv is None:
        argv = []

    if isinstance(subargv, str):
        subargv = pyloco_shlex.split(subargv)

    elif subargv is None:
        subargv = []

    run_profile, run_trace = _extract_option(
            ["--profile", "--trace"], argv, subargv)

    run_debug = True if ("--debug" in argv+subargv) else False

    if parent is None:
        if manager is None:
            parent = PylocoManager(shared=shared)

        else:
            parent = manager(shared=shared)

    if not task:
        if subargv:
            task = GroupCmdTask(parent)

        else:
            task = OptionTask(parent)

    elif isinstance(task, str):

        orgtask = task

        if task == "input" and subargv:
            task_class = GroupInputCmdTask
        else:
            try:
                task_class, argv, subargv, objs = load_taskclass(
                        task, argv, subargv)
            except:
                sys.stderr.write("ERROR: Task '%s' load failure. Please "
                       "check if '%s' is available.\n" % (orgtask, orgtask))
                return out

        if task_class is None:
            sys.stderr.write("ERROR: Task '%s' is not loaded. "
                       "Please check task-path.\n" % orgtask)
            return out

        task = task_class(parent)

        if task is None:
            sys.stderr.write("ERROR: Task '%s' is not created.\n" % orgtask)
            return out

        task._env.update(objs)

    elif type(task) == type(Task) and issubclass(task, Task):

        task = task(parent)

    else:
        sys.stderr.write("ERROR: Task is not found. Please check task-path.\n")
        return out

    if isinstance(task, Task):

        if run_profile:

            try:
                import cProfile as prof

            except ImportError:
                import profile as prof

            prof.runctx('task.run(argv, subargv=subargv, forward=forward)',
                        globals(), locals(), sort=1)
        else:
            if run_trace:
                sys.excepthook = _excepthook
                out = task.run(argv, subargv=subargv, forward=forward)
            elif sys.excepthook == _excepthook:
                out = task.run(argv, subargv=subargv, forward=forward)

            elif run_debug:
                    out = task.run(argv, subargv=subargv, forward=forward)
            else:
                try:
                    out = task.run(argv, subargv=subargv, forward=forward)

                except UsageError as err:
                    print("USAGE ERROR: " + str(err))

                except InternalError as err:
                    print("INTERNAL ERROR: " + str(err))

                except TypeCheckError as err:
                    print("TYPE MISMATCH: " + str(err))

                except NotImplementedError as err:
                    print("NOT IMPLEMENTED: " + str(err))

                except NormalExit:
                    return 0, None

                except SystemExit as err:
                    if err.code != 0:
                        raise SystemExit(err.code)

                    out = 0, None

                except (KeyboardInterrupt, EOFError):
                    print('[Interrupted.]')

                #except Exception as err:
                #    print("ERROR: " + str(err))

    if return_directory:
        os.chdir(return_directory)

    return out


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
