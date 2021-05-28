# -*- coding: utf-8 -*-
"""task module."""

from __future__ import unicode_literals

import sys
import os
import pydoc
import time
import json
import logging
import collections
import pkg_resources
import subprocess
import webbrowser
import websocket

from pyloco.parse import TaskArgParser, PylocoArgParser
from pyloco.proxy import ParentProxy
from pyloco.util import (load_pymod, type_check, pyloco_print, OS, urlparse, teval,
                         split_assert_expr, get_port, pack_websocket_message,
                         is_ipv6, pyloco_import, PylocoPickle, import_modulepath)
from pyloco.error import TestError, InternalError, UsageError
from pyloco.base import Object, Global, pyloco_builtins


def load_taskclass(taskpath, argv, subargv):

    if not taskpath:
        return None, None, None, None

    # TODO: handle aliased task

    if isinstance(taskpath, type):
        if issubclass(taskpath, Task):
            return taskpath, argv, subargv, None

        raise UsageError("Not compatible task type: %s" % type(taskpath))

    # TODO: move to callsite to load_taskclass
    objs = {}

    while "--import" in argv:
        idx = argv.index("--import")
        mpath = argv.pop(idx+1)
        argv.pop(idx)

        key, obj = import_modulepath(mpath)
        objs[key] = obj

    task_class = None

    _p = taskpath.split("#", 1)

    if len(_p) == 2:
        taskpath, fragment = [x.strip() for x in _p]

    else:
        fragment = ""

    if os.path.exists(taskpath):

        mods = []

        if os.path.isfile(taskpath):
            head, base = os.path.split(taskpath)

            if base.endswith(".py"):
                mods.append(load_pymod(head, base[:-3]))

            elif base.endswith(".plx"):
                from pyloco.plxtask import PlXTask
                task_class = PlXTask
                argv.insert(0, taskpath)

            elif base.endswith(".plz"):
                from pyloco.plztask import PlZTask
                task_class = PlZTask
                argv.insert(0, taskpath)

        elif os.path.isdir(taskpath):
            # TODO: support Python package
            pass
            import pdb; pdb.set_trace()

        candidates = {}

        for mod in mods:
            for name in dir(mod):
                if not name.startswith("_"):
                    obj = getattr(mod, name)

                    if (type(obj) == type(Task) and issubclass(obj, Task) and
                            (obj.__module__ is None or
                                not obj.__module__.startswith("pyloco."))):
                       candidates[name] = obj
        if candidates:
            if fragment:
                if hasattr(candidates, fragment):
                    task_class = getattr(candidates, fragment)

                else:
                    raise UsageError("No task is found with a fragment of "
                                     "'%s'." % fragment)
            elif len(candidates) == 1:
                task_class = candidates.popitem()[1]

            else:
                raise UsageError(
                    "More than one frame are found."
                    "Please add fragment to select one: %s" %
                    list(candidates.keys())
                )

        if task_class:
            setattr(task_class, "_path_", os.path.abspath(taskpath))

        #else:
        #    raise UsageError("Task class is not found. Please check path: %s" % taskpath)

    if task_class is None:
        from pyloco.manage import _ManagerBase

        if taskpath in _ManagerBase._default_tasks_:
            task_class = _ManagerBase._default_tasks_[taskpath]

    if task_class is None:
        for ep in pkg_resources.iter_entry_points(group='pyloco.task'):
            if taskpath == ep.name:
                task_class = ep.load()
                from pyloco.plxtask import PlXTask
                if task_class is PlXTask:
                    task_mod = pyloco_import(taskpath)
                    task_dir = os.path.dirname(task_mod.__file__)
                    argv.insert(0, os.path.join(task_dir, getattr(task_mod, "plx")))
                break

    if not task_class:
        from pyloco.mgmttask import mgmt_tasks
        from pyloco.stdtask import standard_tasks
        if taskpath in mgmt_tasks:
            task_class = mgmt_tasks[taskpath]

        elif taskpath in standard_tasks:
            task_class = standard_tasks[taskpath]

# TODO support remote task
#        if not task_class:
#
#            url = urlparse(taskpath)
#
#            if url.netloc or url.scheme:
#                argv.insert(0, taskpath)
#                task_class = RemoteTask

        if not task_class:
            raise UsageError("Task '%s' is not found. Please check path." % taskpath)

    return task_class, argv, subargv, objs


def taskclass(taskpath):
    cls, _, _, _ =  load_taskclass(taskpath, [], [])
    return cls


class Task(Object):
    """Base class for pyloco Tasks



"""

    _version_ = "0.1.0"
    _argparser_ = TaskArgParser

    def __new__(cls, parent, *vargs, **kwargs):

        obj = super(Task, cls).__new__(cls)
        obj.parent = parent
        obj.subargv = None
        obj.taskattr = {}

        if not hasattr(obj, "_name_"):
            obj._name_ = kwargs.pop("name", cls.__name__)

        #obj._parser = TaskArgParser(obj)
        obj._parser = cls._argparser_(obj)

        obj._env = {"__builtins__": pyloco_builtins,
                    "__arguments__": {}}
        obj._fwddefs = {}
        obj._fwds = {}
        obj._shrdefs = {}
        #obj._rdcdefs = {}
        obj._rdcs = {}

        obj._logger = None
        obj._verbose = False

        obj._websocket_server = None
        obj._websocket_client = None
        obj._webserver = None

        obj.tglobal = Global()

        obj.parse_known_args = False
        obj.unknown_args = []

        return obj

    def clone(self):
        Task(self.parent)

    def add_logger(self, logpath):

        root, ext = os.path.splitext(logpath)

        if ext == ".log":
            self.parent.log_setup(filename=logpath)

        else:
            self.parent.log_setup(filename=logpath+".log")

        self._logger = logging.getLogger(self.get_name())

    def _log_level(self, level, *vargs, **kwargs):

        logger = self._logger if self._logger else self.parent._logger

        if logger:
            getattr(logger, level)(*vargs, **kwargs)

    def log_debug(self, *vargs, **kwargs):
        self._log_level("debug", *vargs, **kwargs)

    def log_info(self, *vargs, **kwargs):
        self._log_level("info", *vargs, **kwargs)

    def log_warn(self, *vargs, **kwargs):
        self._log_level("warn", *vargs, **kwargs)

    def log_warning(self, *vargs, **kwargs):
        self._log_level("warning", *vargs, **kwargs)

    def log_error(self, *vargs, **kwargs):
        self._log_level("error", *vargs, **kwargs)

    def log_critical(self, *vargs, **kwargs):
        self._log_level("critical", *vargs, **kwargs)

    def log_exception(self, *vargs, **kwargs):
        self._log_level("exception", *vargs, **kwargs)

    def get_name(self):

        return self.parent.shared["parent_name"] + "." + self._name_

    def get_mgrname(self):

        return self.get_name().split(".")[0]

    def get_proxy(self, proxycls=None, inherit_shared=False):

        if proxycls is None:
            proxycls = ParentProxy

        proxy = proxycls(self)

        if inherit_shared:
            proxy.shared.update(self.parent.shared)

        return proxy

    def _register_check(self, dest):

        if not dest:
            raise UsageError("Incorrect name: %s" % dest)

        if dest.startswith("_"):
            raise UsageError("'Forward-name' should not start with an "
                             "underscore ('_'): %s" % dest)

        if dest in self._fwddefs:
            raise UsageError("'%s' is already registered for forwarding" %
                             dest)

        if dest in self._shrdefs:
            raise UsageError("'%s' is already registered for sharing" % dest)

        #if dest in self._rdcdefs:
        #    raise UsageError("'%s' is already registered for reducing" % dest)

    def register_forward(self, dest, type=None, help=None):

        self._register_check(dest)
        self._fwddefs[dest] = (type, help)

    def register_shared(self, dest, type=None, help=None):

        self._register_check(dest)
        self._shrdefs[dest] = (type, help)

    #def register_reduce(self, dest, type=None, help=None):

    #    self._register_check(dest)
    #    self._rdcdefs[dest] = (type, help)

    def _add_transfer(self, defs, cont, **kwargs):

        for dest, value in kwargs.items():
            if dest not in defs:
                raise UsageError("'%s' is not registered for data transfer." %
                                 dest)

            if type_check(value, defs[dest][0]):
                cont[dest] = value

            else:
                if isinstance(value, str) and os.path.isfile(value):
                    import pdb; pdb.set_trace()     # noqa: E702

                else:
                    raise TestError("Data transfer type check failure: %s" % dest)

    def add_forward(self, **kwargs):

        self._add_transfer(self._fwddefs, self._fwds, **kwargs)

    def add_shared(self, **kwargs):

        self._add_transfer(self._shrdefs, self.parent.shared, **kwargs)

    #def add_reduce(self, **kwargs):

    #    self._add_transfer(self._rdcdefs, self._rcds, **kwargs)

    def write_pickle(self, pickler, data):

        return data

    def pre_perform(self, targs):

        if targs.log:
            self.add_logger(targs.log)

        if targs.verbose:
            self._verbose = True

        if hasattr(targs, "assert_input") and targs.assert_input:

            env = {"__builtins__": pyloco_builtins}

            for k, v in self._env.items():
                if not k.startswith("_"):
                    env[k] = v

            for key, value in targs.__dict__.items():
                if key == "assert_input":
                    continue

                env[key] = value

            for boolexpr in targs.assert_input:
                for varg in boolexpr.vargs:
                    assert_result = eval(varg, env)
                    if assert_result:
                        if self._verbose:
                            pyloco_print('\nINPUT TEST PASSED with "%s"' %
                                         varg)
                    else:
                        pairs = split_assert_expr(varg)

                        if not pairs:
                            raise TestError(
                                "\nINPUT TEST FAILED with '%s' =>"
                                " not True" % varg
                            )

                        elif len(pairs) == 1:
                            sep, (lexpr, rexpr) = pairs.popitem()
                            msg = (
                                "\nINPUT TEST(%s) is FAILED.\n    "
                                "Left expr(%s) of '%s' is evaluated to '%s'"
                                " and\n    right expr(%s) of '%s' "
                                "is evaluated to '%s'.\n"
                            ) % (varg, lexpr, sep, eval(lexpr, env), rexpr,
                                 sep, eval(rexpr, env))

                            raise TestError(msg)

                        else:
                            msg = (
                                "\nINPUT TEST(%s) FAILED: detected multiple"
                                " possibilities of this test failure\n") % varg

                            idx = 0

                            for sep, (lexpr, rexpr) in pairs.items():
                                idx += 1
                                try:
                                    msg += (
                                        "CASE%d:\n    Left expr(%s)" " of"
                                        " '%s' is evaluated to '%s' and\n"
                                        "    right expr(%s) of '%s' is "
                                        "evaluated to '%s'.\n"
                                    ) % (idx, lexpr, sep, eval(lexpr, env),
                                         rexpr, sep, eval(rexpr, env))

                                except Exception:
                                    pass

                            raise TestError(msg)

#        if targs.import_module:
#            modpath = targs.import_module
#            head, base = os.path.split(modpath)                 
#            mod = None
#
#            if os.path.isfile(modpath) and modpath.endswith(".py"):
#                modname = base[:-3]
#                mod = load_pymod(head, modname)
#
#            elif (os.path.isdir(modpath) and
#                    os.path.isfile(os.path.join(modpath, "__init__.py"))): 
#                if base[-1] == os.sep:
#                    modname = base[:-1]
#
#                else:
#                    modname = base
#
#                mod = load_pymod(head, modname)
#
#            else:
#                try:
#                    modname = modpath
#                    mod = pyloco_import(modname)
#
#                except ModuleNotFoundError as err:
#                    raise UsageError("'%s' module is not found." % modname)
#            if mod:
#                self._env[modname] = mod


        if targs.calculate:
            for calc in targs.calculate:
                for expr in calc.vargs:
                    self._env["_"] = teval(expr, self._env)

                for lhs, rhs in calc.kwargs.items():
                    self._env[lhs.strip()] = teval(rhs, self._env)

        if targs.webapp:

            appath = targs.webapp

            # TODO: reuse webserver and websocket
            # TODO: user-provided js can control if reuse or not through
            #       websocket init msg
            if appath.endswith(".js"):
                webapp = os.path.abspath(appath)[:-3]

            elif appath.endswith(".plw"):
                import pdb; pdb.set_trace()     # noqa: E702

            else:
                webapp = os.path.abspath(appath)

            here = os.path.dirname(__file__)

            websocket_port = get_port()
            websocket_path = os.path.join(here, "websocket.py")

            webserver_port = get_port()
            webserver_path = os.path.join(here, "webserver.py")

            self._websocket_server = subprocess.Popen(
                    [sys.executable, websocket_path, str(websocket_port),
                        str(webserver_port)], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT)

            self._webserver = subprocess.Popen(
                [sys.executable, webserver_path, str(webserver_port),
                    str(websocket_port)] + [webapp], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)

            webbrowser.open("http://127.0.0.1:%d" % webserver_port)

            if OS == "windows" and is_ipv6():
                self._websocket_client = websocket.create_connection(
                    "ws://[::1]:%d/" % websocket_port)
            else:
                self._websocket_client = websocket.create_connection(
                    "ws://127.0.0.1:%d/" % websocket_port)

            self._websocket_client.send("pyloco")

            maxiter = 100
            count = 0

            while count < maxiter:
                self._websocket_client.send("check_browser")
                out = self._websocket_client.recv()

                if out == "True":
                    break

                time.sleep(0.1)
                count += 1

    def send_websocket_message(self, sender, msgtype, msg):

        if self._websocket_client:
            self._websocket_client.send(
                json.dumps(pack_websocket_message(sender, msgtype, msg))
            )
            self._websocket_client.recv()

    def post_perform(self, targs):

        if targs.webapp:
            appath = targs.webapp
            wait2close = self.taskattr.get("webapp.wait2close",  True)

            if wait2close:
                if self._websocket_server:
                    pyloco_print("Waiting for '%s' to be completed..." %
                                 appath, end="")
                    sys.stdout.flush()
                    self._websocket_server.communicate(input=None)
                    if self._websocket_client:
                        self._websocket_client.close()

                if self._webserver:
                    self._webserver.communicate(input=None)

                pyloco_print("DONE.")
                sys.stdout.flush()

        env = dict(self._env)
        env.update(self.parent.shared)
        env.update(self._fwds)
        lenv = {}

        if targs.forward:
            try:
                for fwd in targs.forward:
                    for varg in fwd.vargs:
                        self._fwds[varg] = env[varg]

                    for dest, value in fwd.kwargs.items():
                        self._fwds[dest] = eval(value, env, lenv)

            except Exception as err:
                raise UsageError("failed on forwarding: %s" % str(err))

        if targs.shared:
            self._handle_sharedarg(targs.shared)

        if hasattr(targs, "assert_output") and targs.assert_output:

            aenv = {"__builtins__": pyloco_builtins}

            for k, v in self._env.items():
                if not k.startswith("_"):
                    aenv[k] = v

            aenv.update(self.parent.shared)
            aenv.update(self._fwds)

            for boolexpr in targs.assert_output:
                for varg in boolexpr.vargs:
                    assert_result = eval(varg, aenv)

                    if assert_result:
                        if self._verbose:
                            pyloco_print(
                                '\nOUTPUT TEST PASSED with "%s"' % varg
                            )

                    else:
                        pairs = split_assert_expr(varg)

                        if not pairs:
                            raise TestError(
                                "\nOUTPUT TEST FAILED with '%s' =>"
                                " not True" % varg
                            )

                        elif len(pairs) == 1:
                            sep, (lexpr, rexpr) = pairs.popitem()
                            msg = (
                                "\nOUTPUT TEST(%s) is FAILED.\n    "
                                "Left expr(%s) of '%s' is evaluated to '%s'"
                                " and\n    right expr(%s) of '%s' "
                                "is evaluated to '%s'.\n"
                            ) % (varg, lexpr, sep, eval(lexpr, aenv), rexpr,
                                 sep, eval(rexpr, aenv))

                            raise TestError(msg)

                        else:
                            msg = (
                                "\nOUTPUT TEST(%s) FAILED: detected multiple"
                                " possibilities of this test failure\n"
                            ) % varg

                            idx = 0

                            for sep, (lexpr, rexpr) in pairs.items():
                                idx += 1

                                try:
                                    msg += (
                                        "CASE%d:\n    Left expr(%s)" " of"
                                        " '%s' is evaluated to '%s' and\n"
                                        "    right expr(%s) of '%s' is "
                                        "evaluated to '%s'.\n"
                                    ) % (idx, lexpr, sep, eval(lexpr, aenv),
                                         rexpr, sep, eval(rexpr, aenv))

                                except Exception:
                                    pass

                            raise TestError(msg)

        if targs.write_pickle:

            ppf = PylocoPickle()

            data = dict(self.parent.shared)
            data.update(self._fwds)
            data.pop("parent_name", None)

            pdata = self.write_pickle(ppf, data)

            ppf.dump(pdata, targs.write_pickle)

    def write_pickle(self, pickler, data):

        return data

    def read_pickle(self, path):
        import pdb; pdb.set_trace()

    def _handle_sharedarg(self, shared, forwards):

        try:
            env = dict(self._env)
            env.update(forwards)

            for shr in shared:
                for varg in shr.vargs:
                    self.parent.shared[varg] = env[varg]

                for dest, value in shr.kwargs.items():
                    self.parent.shared[dest] = eval(value, env, {})

        except Exception as err:
            raise UsageError("failed on sharing variable: %s" % str(err))

    def run(self, argv, subargv=None, forward=None):
        """task run function
"""
        self.subargv = subargv

        # attribute setting
        if forward is None:
            forward = {}

        elif not isinstance(forward, dict):
            raise InternalError("forward is not a dict type: %s" %
                                str(forward))

        fpenv = {}
        fpenv.update(forward)
        fpenv.update(self.parent.shared)

        if "--read-pickle" in argv:
            idx = argv.index("--read-pickle")
            ppath = argv.pop(idx+1)
            argv.pop(idx)

            ppickle = PylocoPickle()
            penv = ppickle.load(ppath)
            fpenv.update(penv)

        # argument parsing
        targs, self.unknown_args = self._parser.parse_args(argv, fpenv, parse_known_args=self.parse_known_args)

        # pre perform
        self.pre_perform(targs)

        self.send_websocket_message("pyloco", "task", "Task '%s' is started."
                                    % self._name_)

        # perform
        if hasattr(self, "_group_perform"):
            retval = self._group_perform(targs)

        else:
            if "_pathid_" in fpenv and isinstance(fpenv["_pathid_"], int):
                self._env["_pathid_"] = fpenv["_pathid_"]

            retval = self.perform(targs)

        if retval is None:
            retval = 0

        self.send_websocket_message("pyloco", "task", "Task '%s' is finished."
                                    % self._name_)

        # post perform
        self.post_perform(targs)

        _fwds = self._fwds
        self._fwds = {}

        return retval, _fwds

    def perform(self, targs):
        """task perform functiion

Task should implement this function.
"""
        raise NotImplementedError("'perform' method is not implemented in %s." % str(self.__class__))

    def add_data_argument(self, *vargs, **kwargs):
        self._parser.add_data_argument(*vargs, **kwargs)

    def del_data_argument(self, name):
        self._parser.del_data_argument(name)

    def set_data_argument(self, *vargs, **kwargs):
        self._parser.set_data_argument(*vargs, **kwargs)

    def add_option_argument(self, *vargs, **kwargs):
        self._parser.add_option_argument(*vargs, **kwargs)

class OptionTask(Task):

    def _lines(name, title, tasks):

        lines = [title]
        lines.append("-"*len(title))

        for task in sorted(tasks):
            docs = tasks[task].__doc__

            if docs:
                lines.append("{0:10} : {1}".format(task,
                             pydoc.splitdoc(docs)[0]))

            else:
                lines.append("{0:10} : {0}".format(task))

        return lines

    def show_installed_tasks(self, tasks):
        #installed_tasks = dict((n, t) for n, t in tasks.items)
        return self._lines("installed tasks", tasks)

    def show_standard_tasks(self):
        from pyloco.stdtask import standard_tasks
        return self._lines("standard tasks", standard_tasks)

    def show_mgmt_tasks(self):
        from pyloco.mgmttask import mgmt_tasks
        return self._lines("management tasks", mgmt_tasks)

    def run(self, argv, subargv=None, forward=None):

        mgrname = self.parent.get_managerattr("name")
        mgrver = self.parent.get_managerattr("version")

        if not argv:
            print(self.parent.get_managerattr("usage").format(manager=mgrname))
            return 0, None

        usage = self.parent.get_managerattr("usage").format(manager=mgrname)

        if "--verbose" in argv:
            long_desc = self.parent.get_managerattr("long_description")
            list_help = self.parent.get_managerattr("list_help").format(
                    manager=mgrname)
            epilog = self.parent.get_managerattr("epilog")
            desc = long_desc + " " + list_help
            parser = PylocoArgParser(mgrname, mgrver, description=desc,
                                     usage=usage, epilog=epilog)

        else:
            desc = self.parent.get_managerattr("description")
            parser = PylocoArgParser(mgrname, mgrver, description=desc,
                                     usage=usage)

        targs = parser.parse_args(argv)

        if targs.list:

            pyloco_print("")
            pyloco_print("Please run '%s <task> -h' for task-specific "
                         "information." % mgrname)

            # installed

            installed_tasks = collections.OrderedDict()

            default_tasks = self.parent.get_managerattr("default_tasks")
            
            if default_tasks is not None:
                for name, cls in default_tasks.items():
                    installed_tasks[name] = cls

            for ep in pkg_resources.iter_entry_points(group='pyloco.task'):
                if ep.name not in installed_tasks:
                    task_class = ep.load()
                    installed_tasks[ep.name] = task_class

            pyloco_print("")
            for line in self.show_installed_tasks(installed_tasks):
                pyloco_print(line)

            pyloco_print("")
            for line in self.show_standard_tasks():
                pyloco_print(line)

            pyloco_print("")
            for line in self.show_mgmt_tasks():
                pyloco_print(line)

        elif targs.verbose:
            parser.print_help()

        return 0, None


class RemoteTask(Task):
    """Remote task

        RemoteTask downloads a remote task and runs it locally.
    """

    _version_ = "0.1.0"

    def run(self, argv, subargv=None, forward=None):

        raise Exception("REMOTETASK")
        import pdb; pdb.set_trace()     # noqa: E702

class StandardTask(Task):

    _installation_ = """'{name}' task is one of pyloco standard tasks.
Standard tasks are already installed when pyloco was installed."""

class ManagementTask(Task):

    _installation_ = """'{name}' task is one of pyloco management tasks.
Management tasks are always available once pyloco is installed."""
