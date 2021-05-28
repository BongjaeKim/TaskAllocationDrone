# -*- coding: utf-8 -*-
"""grouptask and multitasking module."""

from __future__ import unicode_literals

import os
import uuid
import random
import collections
import functools
import multiprocessing
import traceback
#from six import with_metaclass

from pyloco.test import TestCase
from pyloco.task import Task
from pyloco.proxy import Proxy
from pyloco.util import pyloco_print, _place_holder, pyloco_shlex, parse_param_option
from pyloco.base import Object
from pyloco.error import UsageError, InternalError

_mypipe = None

class RemoteProxy(Proxy):
    (_MP_MSG_FINISHED, _MP_MSG_TERMINATE, _MP_MSG_CLIENTPROXY,
     _MP_MSG_ERROR, _MP_MSG_PUSH, _MP_MSG_PIPE, _MP_MSG_LOG) = range(7)


class _LoggerWrapper(object):
        
    def __init__(self, pipe, pathid):
        self.pipe = pipe
        self.pathid = pathid

    def _level(self, level, *vargs, **kwargs):
        self.pipe.send((self.pathid, RemoteProxy._MP_MSG_LOG, (level, vargs, kwargs)))

    def debug(self, *vargs, **kwargs):
        self._level("debug", *vargs, **kwargs)

    def info(self, *vargs, **kwargs):
        self._level("info", *vargs, **kwargs)

    def warn(self, *vargs, **kwargs):
        self._level("warn", *vargs, **kwargs)

    def warning(self, *vargs, **kwargs):
        self._level("warning", *vargs, **kwargs)

    def error(self, *vargs, **kwargs):
        self._level("error", *vargs, **kwargs)

    def critical(self, *vargs, **kwargs):
        self._level("critical", *vargs, **kwargs)

    def exception(self, *vargs, **kwargs):
        self._level("exception", *vargs, **kwargs)


class ServerProxy(RemoteProxy):
    """Server proxy

        To MultitaskTask of a parent process, this proxy acts as a sub-task
    """

    def __init__(self, task, pipe):
        self.task = task
        self.pipe = pipe
        self.forward = {}
        self.retval = 0
        self.pending_msgs = []

        self.pipe.send(True)

    def __getattr__(self, attr):

        try:
            return getattr(self.task.parent, attr)

        except Exception:
            raise UsageError(
                "'ServerProxy' object has no attribute '%s'" % attr)

    def handle_message(self):

        msgid = None

        try:
            if self.pipe.poll():
                self.pending_msgs.append(self.pipe.recv())

            if self.pending_msgs:
                sender_pathid, msgid, item = self.pending_msgs.pop(0)

                self.task.log_debug("from SUBPATH %d: msgid=%d, item=%s" %
                                    (sender_pathid, msgid, item))

                if msgid == self._MP_MSG_CLIENTPROXY:
                    proxycall = item.pop("__proxycall__", None)

                    if proxycall:
                        vargs = item.pop("__vargs__", [])

                        try:
                            values = getattr(self.task.parent, proxycall)(
                                *vargs, **item)
                            self.pipe.send((sender_pathid,
                                            self._MP_MSG_CLIENTPROXY, values))

                        except Exception:
                            self.task.log_debug("Proxycall error from SUBPATH %d: %s" %
                                    (sender_pathid, str(err)))

                            msgid = self._MP_MSG_ERROR
                    else:
                        msgid = self._MP_MSG_ERROR

                elif msgid == self._MP_MSG_FINISHED:
                    self.forward = item
                    self.pipe.send((sender_pathid, self._MP_MSG_FINISHED, True))

                elif msgid == self._MP_MSG_PUSH:
                    for var, value in item.items():
                        if var in self.parent.shared:
                            if isinstance(self.parent.shared, dict):
                                if sender_pathid in self.parent.shared[var]:
                                    # other subtask's variable
                                    self.task.log_error(
                                        "Dupulicated subtask variable : %s" %
                                        var)
                                else:
                                    self.parent.shared[var][sender_pathid] = value
                            else:
                                # parent variables
                                self.task.log_error(
                                    "Dupulicated parent task variable : %s" %
                                    var)
                        else:
                            self.parent.shared[var] = {}
                            self.parent.shared[var][sender_pathid] = value

                elif msgid == self._MP_MSG_TERMINATE:
                    self.task.log_debug("TERM REQ: %d, %s" % (sender_pathid, str(item)))
                    self.pipe.send((sender_pathid, self._MP_MSG_TERMINATE, item))

                elif msgid == self._MP_MSG_LOG:
                    f, v, k = item
                    getattr(self.task, "log_"+f)(*v, **k)

                elif msgid == self._MP_MSG_ERROR:
                    self.task.log_error("from SUBTASK %d: %s" %
                                        (sender_pathid, item))

                else:
                    self.task.log_error(
                        "from SUBTASK %d: Unknown message id of %d" %
                        (sender_pathid, msgid)
                    )

        except EOFError:

            self.task.log_error("from SUBTASK %d: End of File Error" %
                                sender_pathid)

        return msgid

    def get_forward(self):
        return self.forward

    def get_retval(self):
        return self.retval

    def set_retval(self, val):
        self.retval = val


def _client_wrapper(*vargs, **kwargs):

    func = kwargs.pop("_original_function", None)
    if func is None:
        raise Exception("ClientProxy could not find the original function.")

    pipe = kwargs.pop("_message_pipe", None)
    if pipe is None:
        raise Exception("ClientProxy has no message pipe.")

    msgid = kwargs.pop("_proxy_msg_id", None)
    pathid = kwargs.pop("_proxy_pathid", None)

    kwargs["__proxycall__"] = func
    kwargs["__vargs__"] = vargs
    pipe.send((pathid, msgid, kwargs))
    sgid_from, msgid, values = pipe.recv()
    return values


class ClientProxy(RemoteProxy):
    """Client proxy

        To GroupTask of a child process, this proxy acts as a parent
        proxy of MultitaskTask
    """

    def __init__(self, parent_attrs, pathid, pipe):

        self.task = _place_holder()
        self.pathid = pathid
        self.pipe = pipe
        self.shared = parent_attrs if parent_attrs else {}

    def __getattr__(self, attr):

        if attr == "_logger":
            return _LoggerWrapper(self.pipe, self.pathid)

        else:
            return functools.partial(
                _client_wrapper, _original_function=attr,
                _message_pipe=self.pipe,
                _proxy_msg_id=self._MP_MSG_CLIENTPROXY, _proxy_pathid=self.pathid
            )

    def terminate(self, forward):
        self.pipe.send((self.pathid, self._MP_MSG_FINISHED, forward))
        self.pipe.recv()
        self.pipe.send((self.pathid, self._MP_MSG_TERMINATE, None))
        self.pipe.recv()

    def push_data(self, pushes):
        # pushes : dict of values
        self.pipe.send((self.pathid, self._MP_MSG_PUSH, pushes))


class TaskPath(object):

    _ids = 0

    def __init__(self, tasks=None):

        self._tasks = [] if tasks is None else tasks
        self._pathid_ = self._ids
        self._ids += 1

    def clone(self):

        obj = TaskPath(tasks=list(self._tasks))
        obj._pathid_ = self._ids
        self._ids += 1
        return obj

    def append_task(self, task, argv=[], subargv=[]):

        self._tasks.append((task, argv, subargv))

    def run(self, parent, forward, extra_args, params):

        from pyloco.task import load_taskclass, Task

        out = 0
        out_forward = None

        for task, argv, subargv in self._tasks:
            
            task_class, argv, subargv, objs = load_taskclass(task, argv + extra_args, subargv)

            if task_class is None:
                raise UsageError("Task '%s' is not loaded." % str(task))

            taskobj = task_class(parent)

            if taskobj is None:
                raise InternalError("Task '%s' is not created." % str(task))

            #with open("taskpath.%d.log"%os.getpid(), "w") as f:
            #    f.write("\n\n".join([str(taskobj), str(parent)]))
            #    f.flush()

            if isinstance(taskobj, Task):
                forward["_pathid_"] = self._pathid_
                taskobj._env.update(objs)
                taskobj._env.update(params)
                out, forward = taskobj.run(argv, subargv=subargv, forward=forward)
                out_forward = forward

            else:
                raise UsageError("Task '%s' is not a Task type." % str(task))

        return out, out_forward


class Arrival(Object):

    def __new__(cls, *vargs, **kwargs):

        self = Object.__new__(cls)
        self._arrival_setup()
        return self

    def add_arrival_path(self, path):

        self._arrival_paths.append(path)

    def _arrival_setup(self):

        self._arrival_paths = []

    def reduce_data(self, forwards):
        return {}

    def check_quorum(self, paths):

        return all((p in paths) for p in self._arrival_paths)

class Departure(Object):

    def __new__(cls, *vargs, **kwargs):

        self = Object.__new__(cls)
        self._departure_setup()
        return self

    def add_departure_path(self, path):

        self._departure_paths.append(path)

    def get_readypaths(self):

        return self._departure_paths

    def _departure_setup(self):

        self._departure_paths = []
        self.departure_data = {}
        self.departure_argument = {}
        self.departure_parameter = {}

    def map_data(self, paths, reduced):
        pass


class TaskHub(Departure, Arrival):

    def __new__(cls, *vargs, **kwargs):

        self = super(TaskHub, cls).__new__(cls)
        self._departure_setup()
        self._arrival_setup()
        return self

class EntryHub(Departure):

    def __new__(cls, *vargs, **kwargs):

        self = super(EntryHub, cls).__new__(cls)
        return self

    def load_data(self, path, **data):

        if path in self.departure_data:
            self.departure_data[path].update(data)

        else:
            self.departure_data[path] = data

    def append_argument(self, path, arg):

        if isinstance(arg, str):
            arg = pyloco_shlex.split(arg)

        if path in self.departure_data:
            self.departure_argument[path].extend(arg)

        else:
            self.departure_argument[path] = arg

    def append_parameter(self, path, params):

        if path in self.departure_data:
            self.departure_parameter[path].update(params)

        else:
            self.departure_parameter[path] = params

class TerminalHub(Arrival):

    def __new__(cls, *vargs, **kwargs):

        self = super(TerminalHub, cls).__new__(cls)
        return self

    def forward_data(self, reduced):
        return {}

    def shared_data(self, reduced):
        return {}

def _procinit(pipes, lock):

    global _mypipe

    with lock:
        for pipe in pipes:
            if pipe.poll():
                pipe.recv()
                _mypipe = pipe
                break 

    if not _mypipe:
        raise InternalError("No pipe is assigned to subprocess.")

def _launch_taskpath(path, forward, extra_args, params, shared):

    out = 0

    try:
        parent = ClientProxy(shared, path._pathid_, _mypipe)
        out, forward = path.run(parent, forward, extra_args, params)
        _mypipe.send((path._pathid_, ClientProxy._MP_MSG_FINISHED, forward))
        recv_pathid, msgid, ack = _mypipe.recv()

    except Exception as err:
        #exc_type, exc_obj, exc_tb = sys.exc_info()
        errinfo = str(err) + " : " + str("\n".join(traceback.format_stack()))
        _mypipe.send((path._pathid_, ClientProxy._MP_MSG_ERROR, errinfo))

    _mypipe.send((path._pathid_, ClientProxy._MP_MSG_TERMINATE, None))
    recv_pathid, msgid, ack = _mypipe.recv()

    return out, forward


class GroupTask(Task, EntryHub, TerminalHub):
    """Base task for pyloco group tasks
"""

    _version_ = "0.1.0"
    _name_ = "group"

    def __new__(cls, parent, *vargs, **kwargs):

        self = super(GroupTask, cls).__new__(cls, parent, *vargs, **kwargs)

        self._arrival_setup()
        self._departure_setup()

        self.add_option_argument(
            "--multiproc", metavar="param-list", type=str, param_parse=True,
            help="(E,P) control creation and completion of multiple processes")

        self.add_option_argument(
            "--inherit-shared", action="store_true", help="inherit shared data from parent")

        #self.add_option_argument(
        #    "--reduce", metavar="param-list", type=str, param_parse=True,
        #    action="append", help="(E,P) reducing data from sub-tasks.")

        self.nprocs = None
        self._server_proxies = []
        self.taskpaths = collections.OrderedDict()
        self._procpool = None
        self._arrivals = []
        self._departures = []
        #self.shared = {}

        return self

    def _handle_sharedarg(self, shared):
        # TODO: need this?
        try:
            for shr in shared:
                for varg in vargs:
                    self.parent.shared[varg] = env[varg]

                for dest, value in shr.kwargs.items():
                    self.parent.shared[dest] = eval(value, env, lenv)

        except Exception as err:
            raise UsageError("failed on sharing variable: %s" % str(err))

    def enable_multiprocessing(self, opt):

        self.nprocs = opt.vargs[0]

        if len(opt.vargs) > 1:
            multiprocessing.set_start_method(opt.vargs[1])

    def copy_taskpath(self, path, ncopies, cloned_only=False):

        clones = []

        if not cloned_only and ncopies > 0:
            clones.append(path)
            ncopies -= 1

        clones.extend([path.clone() for n in range(ncopies)])

        return clones

    def connect_taskpath(self, departure, path, arrival):

        if departure not in self._departures:
            self._departures.append(departure)

        departure.add_departure_path(path)

        if arrival not in self._arrivals:
            self._arrivals.append(arrival)

        arrival.add_arrival_path(path)

        self.taskpaths[path] = (departure, arrival)

    def idle_perform(self, targs):
        pass

    def _create_procpool(self, nprocs):

        cpipes = []

        for idx in range(nprocs):
            _spipe, _cpipe = multiprocessing.Pipe()
            cpipes.append(_cpipe)
            self._server_proxies.append(ServerProxy(self, _spipe))

        return multiprocessing.Pool(nprocs, initializer=_procinit,
                                    initargs=(cpipes, multiprocessing.Lock()))

    def _group_perform(self, targs):

        out = 0
        clsname = self.__class__.__name__

        if targs.multiproc:
            self.enable_multiprocessing(targs.multiproc)

        self.perform(targs)

        path_queue = self.get_readypaths()

        if not path_queue:
            return out

        parent = self.get_proxy(inherit_shared=targs.inherit_shared)

        if self.nprocs == "*":
            self._procpool = self._create_procpool(multiprocessing.cpu_count())

        elif isinstance(self.nprocs, str) and self.nprocs.isdigit():
            self._procpool = self._create_procpool(int(self.nprocs))
        
        self.log_debug("PATH ENQUE @ %s:\n    %s" % (clsname, str("\n    ".join([str(p) for p in path_queue]))))
        active_departures = {self:[]}
        active_arrivals = {}
        async_results = []
        
        while path_queue or any(not r[0].ready() for r in async_results):

            ready_paths = []
            performed_taskpaths = []


            for idx in range(len(path_queue)-1, -1, -1):
                departure, arrival = self.taskpaths[path_queue[idx]]
                if departure in active_departures:
                    path = path_queue.pop(idx)
                    data = departure.departure_data.get(path, {})
                    args = departure.departure_argument.get(path, [])
                    params = departure.departure_parameter.get(path, [])
                    ready_paths.append((path, data, args, params))
                    self.log_debug("APPEND PATH @ %s:\n    %s" % (clsname, str("\n    ".join([str(p) for p in ready_paths[-1]]))))

            if self._procpool is None:
                for path, data, args, params in ready_paths:
                    out, fwd = path.run(parent, data, args, params)
                    performed_taskpaths.append((path, out, fwd))

            elif ready_paths:
                for path, data, args, params in ready_paths:
                    res = self._procpool.apply_async(_launch_taskpath, (path, data, args, params, self.parent.shared), {})
                    async_results.append((res, path))
                    self.log_debug("APPEND ASYNC @ %s:\n    %s" % (clsname, str("\n    ".join([str(p) for p in async_results[-1]]))))
            else:
                for server_proxy in self._server_proxies:
                    message = server_proxy.handle_message()

                self.idle_perform(targs)

            if async_results:
                for idx in range(len(async_results)-1, -1, -1):
                    res = async_results[idx][0]
                    if res.ready():
                        _, path = async_results.pop(idx)
                        self.log_debug("ASYNC READY @ %s:\n    %s" % (clsname, str("\n    ".join([str(r) for r in [path._pathid_, path]]))))
                        out, fwd = res.get()
                        performed_taskpaths.append((path, out, fwd))
                        self.log_debug("ASYNC GET @ %s:\n    %s" % (clsname, str("\n    ".join([str(r) for r in [path, out, fwd]]))))

            # TODO: support dynamic graph?
            if performed_taskpaths:

                # (path, out, fwd)
                for performed in performed_taskpaths:
                    arrival = self.taskpaths[performed[0]][1]

                    if arrival in active_arrivals:
                        active_arrivals[arrival].append(performed)

                    else:
                        active_arrivals[arrival] = [performed]

                    self.log_debug("PERFORMED @ %s:\n    %s" % (clsname, str("\n    ".join([str(p) for p in [arrival, performed[0]]]))))

                allpaths_arrived = []

                for arrival, arrival_paths in active_arrivals.items():
                    paths = [p[0] for p in arrival_paths]
                    if arrival.check_quorum(paths):
                        self.log_debug("ALL ARRIVED @ %s:\n    %s" % (clsname, str(arrival)))
                        allpaths_arrived.append(arrival)

                for arrival in allpaths_arrived:
                    forwards = {}

                    for path, out, fwd in active_arrivals.pop(arrival):
                        forwards[path._pathid_] = fwd

                    reduced = arrival.reduce_data(forwards)

                    if not reduced:
                        reduced = {}

                    if isinstance(arrival, TerminalHub):
                        fwd = arrival.forward_data(reduced)

                        if fwd:
                            self.add_forward(**fwd)

                        shr = arrival.shared_data(reduced)

                        if shr:
                            self.add_shared(**shr)

                        break

                    elif isinstance(arrival, Departure):
                        if arrival not in active_departures:
                            active_departures[arrival] = []

                        paths = arrival.get_readypaths()

                        for path in paths:
                            if path not in arrival.departure_data:
                                arrival.departure_data[path] = {}

                        arrival.map_data(paths, reduced)
                        path_queue.extend(paths)
                        self.log_debug("PATH ENQUE @ %s:\n    %s" % (clsname, str("\n    ".join([str(p) for p in paths]))))

        if self._procpool is not None:
            self._procpool.close()
            self._procpool.join()

        return out

#    def __init__(self, parent):
#
#        self._task_table = {}
#        self._parser = GroupArgParser(self)
#
#    def run(self, argv, subargv=None, forward=None):
#
#        self._group_forwarded = forward
#        return super(GroupTask, self).run(argv, subargv, forward)

#    def perform(self, targs):
#        """execute sub-tasks
#
#"""
#
#        out = 0
#        subargv = self.subargv
#
#        env = dict(self._env)
#        env.update(self.parent.shared)
#
#        if subargv:
#            parent = self.get_proxy()
#
#            if targs.repeat:
#                nrepeat = eval(targs.repeat.vargs[0], env, {})
#                org_subargv = list(subargv)
#
#                while nrepeat > 1:
#                    subargv.append("--")
#                    subargv.extend(org_subargv)
#                    nrepeat -= 1
#
#                for kwargs in targs.repeat.kwargs:
#                    import pdb; pdb.set_trace()     # noqa: E702
#
#            if targs.arrange == "column":
#                self._task_table[0] = {"subargv": subargv}
#
#            elif targs.arrange == "rank":
#                rank = 0
#                while "--" in subargv:
#                    idx = subargv.index("--")
#                    self._task_table[rank] = {"subargv": subargv[:idx]}
#                    rank += 1
#                    subargv = subargv[idx+1:]
#
#                if subargv:
#                    self._task_table[rank] = {"subargv": subargv}
#
#            else:
#                raise UsageError("Unknown arrange: %s" % targs.arrange)
#
#        # [<N>|'ranks'|'cores'],padding=['clone'|'none'],extra=['discard'|'wrap']
#        if targs.multiproc:
#
#            if not targs.multiproc.vargs:
#                raise UsageError("No indication of the number of processes "
#                                 "in multiprocessing.")
#
#            out, _fwds = run_multiproc(self, targs, env)
#
#        else:
#
#            for rank in sorted(self._task_table.keys()):
#                rankfwd = {}
#                env["__rank__"] = rank
#                env["_R"] = rank
#
#                try:
#                    if self._group_forwarded:
#                        rankfwd.update(self._group_forwarded)
#
#                    if targs.forward:
#                        for fwd in targs.forward:
#                            for varg in fwd.vargs:
#                                rankfwd[varg] = env[varg]
#
#                            for dest, value in fwd.kwargs.items():
#                                rankfwd[dest] = eval(value, env, {})[0]
#
#                    self._task_table[rank]["forward"] = rankfwd
#
#                except Exception as err:
#                    raise UsageError("failed on distributing: %s" % str(err))
#
#            targs.forward = None
#
#            out, _fwds = run_task_table(self._task_table, parent)
#
#        # collect data from server_proxies
#        if targs.reduce:
#            env["__forwards__"] = _fwds
#            env["_F"] = _fwds
#
#            for opt in targs.reduce:
#                for varg in opt.vargs:
#                    env[varg] = eval(varg, env, {})
#                    self._fwds[varg] = env[varg]
#
#                for key, value in opt.kwargs.items():
#                    env[key] = eval(value, env, {})
#                    self._fwds[key] = env[key]
#
#        elif len(_fwds) == 1:
#            self._fwds.update(_fwds.popitem()[1])
#
#        self._task_table = []
#
#        return out


class GroupCmdTask(GroupTask):

    def __init__(self, parent):

        self.add_groupcmd_arguments()
        self._data = {}
        self._reduce_args = None

    def add_groupcmd_arguments(self):

        self.add_option_argument(
            "--clone", metavar="N", param_parse=True,
            help="(E,P) generate N copies of this command including the command")

        self.add_option_argument(
            "--reduce", metavar="param-list", type=str, param_parse=True,
            action="append", help="(E,P) copying data from sub-tasks "
            "and forward it to next task")

    def _append_task(self, path, items):

        if len(items) < 1:
            raise UsageError("task is not found: %s" % str(self.subargv))

        if items[0].startswith("-"):
            raise UsageError("First argument is not a task reference: %s" % str(items))

        path.append_task(items[0], argv=items[1:])
        del items[:]

    def perform(self, targs):

        path = TaskPath()

        items = []
        for s in self.subargv:
            if s == "--":
                self._append_task(path, items)

            else:
                items.append(s)

        if items:
            self._append_task(path, items)

        # clone if specified in argv
        if targs.clone:
            evaluated = parse_param_option(str(targs.clone), True, self._env)
            argument = evaluated.kwargs.pop("_argument_", None)

            if evaluated.vargs:
                numclone = len(evaluated.vargs)

            elif argument:
                numclone = len(argument)

            elif evaluated.kwargs:
                numclone = len(list(evaluated.kwargs.values())[0])

            else:
                raise UsageError("No data for clone is specified.")

            for idx, path in enumerate(self.copy_taskpath(path, numclone)):
                self.connect_taskpath(self, path, self)

                if evaluated.vargs:
                    if len(evaluated.vargs) != numclone:
                        raise UsageError("The number of clone data mismatch")

                    self.load_data(path, data=evaluated.vargs[idx])

                if argument:
                    if len(argument) != numclone:
                        raise UsageError("The number of clone data mismatch")

                    self.append_argument(path, argument[idx])

                if evaluated.kwargs:
                    params = {}

                    for k, v in evaluated.kwargs.items():
                        if len(v) != numclone:
                            raise UsageError("The number of clone data mismatch")
                        params[k] = v[idx]

                    self.append_parameter(path, params)

        else:
            self.connect_taskpath(self, path, self)
            self.load_data(path, **self._data)

        if targs.reduce:
            self._reduce_args = targs.reduce

    def reduce_data(self, forwards):

        # --reduce 'x=(lambda x,y: x+y, plots)'
        if self._reduce_args:
            fwds = {}

            for pathid, fwd in forwards.items():
                for k, v in fwd.items():
                    if k in fwds:
                        fwds[k].append(v)

                    else:
                        fwds[k] = [v]

            for opt in self._reduce_args:
                for key, value in opt.kwargs.items():
                    self._fwds[key] = functools.reduce(*eval(value, fwds, {})) 

        return {}


class DefaultGroupTestCase(TestCase):

    _testargs_ = []

    def test_default(self):
        from pyloco.manage import PylocoManager

        task = GroupCmdTask(PylocoManager())
        out = task.run([], subargv=self._testargs_)
