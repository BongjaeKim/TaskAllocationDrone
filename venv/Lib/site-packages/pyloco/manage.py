# -*- coding: utf-8 -*-
"""manager module."""

from __future__ import unicode_literals

import sys
import os
import threading
import inspect
import logging
import copy
import json
import abc
import ast
# import jsonschema

from pyloco.task import Task
from pyloco.error import InternalError, UsageError
from pyloco.util import PY3, import_modulepath
from pyloco.base import Object

# schema of pyloco config v1
pyloco_config_version_1 = {
    "type": "object",
    "properties": {
        "config_version": {"type": "number"},
    },
}

pyloco_config_defaults = {
    "config_version": 1
}

pyloco_manager_defaults = {
    "config_version": 1
}


class _Manager(object):

    _instances = {}

    def __new__(cls, name):

        if name not in cls._instances:
            cls._instances[name] = super(_Manager, cls).__new__(cls)

        elif cls is not cls._instances[name].__class__:
            raise InternalError("'%s' manager class mismatch: %s != %s" %
                                (name, cls.__name__,
                                cls._instances[name].__class__.__name__))

        return cls._instances[name]

    def __init__(self, name):

        self._config, self._manager = self._get_pyloco_config(name)
        self._log_enabled = False
        self._logger = None

    def _check_pyloco_config(self, path):

        # TODO: update code if config syntax version mismatches

        with open(path) as f:
            cfg = json.load(f)
            # jsonschema.validate(instance=cfg, schema=pyloco_config_version_1)

        return cfg

    def _get_pyloco_config(self, name):

        home = os.path.expanduser("~")
        pyloco_home = os.path.join(home, ".pyloco")

        if not os.path.exists(pyloco_home):
            os.makedirs(pyloco_home)

        if not os.path.isdir(pyloco_home):
            raise InternalError("'%s' is not a directory." % pyloco_home)

        cfgobj = None
        config = os.path.join(pyloco_home, ".config")

        if os.path.exists(config):
            if not os.path.isfile(config):
                raise InternalError("'%s' is not a pyloco configuration file."
                                    % config)

            cfgobj = self._check_pyloco_config(config)

        else:
            with open(config, "w") as f:
                json.dump(pyloco_config_defaults, f)

            cfgobj = copy.deepcopy(pyloco_config_defaults)

        mgrobj = None
        manager = os.path.join(pyloco_home, name)

        if os.path.exists(manager):
            if not os.path.isfile(manager):
                raise InternalError("'%s' is not a manager configuration file."
                                    % manager)

            mgrobj = self._check_pyloco_config(manager)

        else:
            cfg = getattr(self, "_config_", pyloco_manager_defaults)

            with open(manager, "w") as f:
                json.dump(cfg, f)

            mgrobj = copy.deepcopy(cfg)

        return cfgobj, mgrobj
        
    def log_setup(self, filename="pyloco.log", filemode="w",
                  format='%(name)s - %(levelname)s - %(message)s',
                  level=logging.DEBUG):

        if not self._log_enabled:
            logging.basicConfig(filename=filename, filemode=filemode,
                                format=format, level=level)

class _ManagerBase(object):

    _usage_ = ("{manager} [{manager}-arg...]|[task [task-arg...]]\n"
            "              [-- task [task-arg...]]...\n"
    )
    _help_help_ = "Please run '{manager} -h' for details of {manager} arguments." 
    _list_help_ = ("Please run '{manager} -l' for a list of locally "
                   "available tasks.")
    _default_tasks_ = {}

    def __init__(self, shared=None):

        self.shared = shared if isinstance(shared, dict) else {}
        if "parent_name" not in self.shared:
            self.shared["parent_name"] = self._name_

        self._manager = _Manager(self._name_)

        self._lock = threading.RLock()

    def __getattr__(self, attr):

        with self._lock:
            return getattr(self._manager, attr)

        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, attr))

    def get_managerattr(self, attr):

        return getattr(self, "_%s_" % attr, None)

    @classmethod
    def load_default_task(cls, *tasks, **kwargs):

        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        mgrdir = os.path.realpath(os.path.abspath(os.path.dirname(
                 module.__file__)))

        for task in tasks:

            _p = task.split("#", 1)

            if len(_p) == 2:
                taskpath, fragment = [x.strip() for x in _p]

            else:
                taskpath = task
                fragment = ""

            taskmodpath = os.path.realpath(os.path.abspath(os.path.join(mgrdir, taskpath)))

            if os.path.exists(taskmodpath):

                modname, mod = import_modulepath(taskmodpath)
                if modname not in sys.modules:
                    raise InternalError("'%s' task is not loaded." % task)

                task_class = None
                candidates = {}

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
            else:
                raise UsageError("'%s' does not exist within this manager." % task)


            if task_class:
                cls._default_tasks_[task_class._name_]= task_class

            else:
                raise UsageError("'%s' task is not loaded." % task)

    @classmethod
    def main(cls, *vargs, **kwargs):
        from pyloco.main import main

        kwargs["manager"] = cls
        return main(*vargs, **kwargs)

    @classmethod
    def perform(cls, *vargs, **kwargs):
        from pyloco.main import perform

        kwargs["manager"] = cls
        return perform(*vargs, **kwargs)

if PY3:
    class Manager(_ManagerBase):

        @property
        @abc.abstractmethod
        def _name_(self):
            raise NotImplementedError("'%s' has not '_name_' attribute" %
                                      self.__class__.__name__)

        @property
        @abc.abstractmethod
        def _version_(self):
            raise NotImplementedError("'%s' has not '_version_' attribute" %
                                      self.__class__.__name__)

else:
    class Manager(_ManagerBase):

        @abc.abstractproperty
        def _name_(self):
            raise NotImplementedError("'%s' has not '_name_' attribute" %
                                      self.__class__.__name__)

        @abc.abstractproperty
        def _version_(self):
            raise NotImplementedError("'%s' has not '_version_' attribute" %
                                      self.__class__.__name__)

class PylocoManager(Manager):
    "Pyloco default manager"

    _name_ = "pyloco"
    _version_ = "0.0.139"
    _author_ = "Youngsung Kim"
    _author_email_ = "grnydawn@gmail.com"
    _url_ = "https://github.com/grnydawn/pyloco"
    _license_ = "Apache License 2.0"
    _description_ = "Python Microapplication Launcher"
    _long_description_ = """
"pyloco" executes a composable Python microapplication, or a task.
"""
    _epilog_ = ("Please visit 'http://pyloco.net' for pyloco online "
                "documentation")

# lock file for sync processes

#        lock_filename = '/tmp/sample-locking.lock'
#        lock_file = open(lock_filename, 'w')
#        try:
#            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
#        except IOError:
#            print('Cannot lock: ' + lock_filename)
#            return False
#        print('Locked! Running code...')

def collect_mgrattrs(filename, clsname):

    attrs = {}

    with open(filename) as f:
        tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == clsname:
                for cnode in node.body:
                    if (isinstance(cnode, ast.Assign) and len(cnode.targets)==1
                            and cnode.targets[0].id.startswith("_")
                            and cnode.targets[0].id.endswith("_")):
                        if isinstance(cnode.value, ast.Str):
                            attrs[cnode.targets[0].id] = cnode.value.s
                        elif isinstance(cnode.value, ast.List):
                            l = []
                            for elt in cnode.value.elts:
                                l.append(elt.s)
                            attrs[cnode.targets[0].id] = l
                        else:
                            print("Warning: unsupported manager attribute "
                                  "type: %s" % cnode.value.__class__.__name__)
    return attrs
