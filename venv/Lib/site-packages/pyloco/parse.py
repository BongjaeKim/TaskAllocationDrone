# -*- coding: utf-8 -*-
"""parser object module."""

from __future__ import unicode_literals

import os
import argparse
import pydoc
import pickle
import re

from pyloco.util import (pyloco_formatter, parse_param_option, type_check,
                         Option)
from pyloco.error import UsageError, NormalExit, TypeCheckError

_pat_dest = r"\$[^\d\W]\w*\$"

_re_dest = re.compile(_pat_dest)

class PylocoArgParser(argparse.ArgumentParser):

    def __init__(self, name, version, *vargs, **kwargs):

        #if "usage" not in kwargs:
        #    kwargs["usage"] = "Usage is not available."

        #if "description" not in kwargs:
        #    kwargs["description"] = "Description is not available."

        kwargs["add_help"] = False

        super(PylocoArgParser, self).__init__(*vargs, **kwargs)

        group = self.add_argument_group('%s arguments' % name)

        group.add_argument("-l", "--list", action="store_true",
                           help="list locally available tasks")
        group.add_argument("-h", "--help", action="help",
                           help="show help message for arguments")
        group.add_argument("--verbose", action="store_true",
                           help="show long help")
        group.add_argument("--log", metavar="log-path",
                           help="activate application-level logging")
        group.add_argument('--version', action='version', 
                           version=name + " " + version,
                           help="show version")


class _TaskArgParser(argparse.ArgumentParser):

    def __init__(self, *vargs, **kwargs):

        super(_TaskArgParser, self).__init__(*vargs, **kwargs)
        self.pos_required = {}

    def _get_positional_kwargs(self, dest, **kwargs):
        # make positional can handle required

        required = kwargs.pop("required", True)
        self.pos_required[dest] = required
        kwargs = super(_TaskArgParser, self)._get_positional_kwargs(
                dest, **kwargs)
        kwargs["required"] = False

        return kwargs


class ArgType(object):

    def __init__(self, arg_type, arg_action, arg_nargs, evaluate,
                 param_parse, env):
        self.dest = None
        self.arg_type = arg_type
        self.arg_action = arg_action
        self.arg_nargs = arg_nargs
        self.evaluate = evaluate
        self.param_parse = param_parse
        self.env = env

    def _tryconv(self, out):

        try:
            return self.arg_type(out)

        except Exception as err:
            raise TypeCheckError(out, self.arg_type)

    def __call__(self, data):

        self.env["__defer__"] = not self.evaluate
        l1 = data.replace("{", "{{").replace("}", "}}")
        l2 = l1.replace("_{{", "{").replace("}}_", "}")
        data = pyloco_formatter.vformat(l2, [], self.env)
        #data = pyloco_formatter.vformat(data, [], self.env)
        self.env.pop("__defer__")

        if self.param_parse:
            out = parse_param_option(data, self.evaluate, self.env)

        elif self.evaluate:
            out = eval(data, self.env, {})

        else:
            out = data

        if isinstance(out, Option):
            for varg in out.vargs:
                if not type_check(varg, self.arg_type):
                    out = self._tryconv(varg)

            for kwarg in out.kwargs.values():
                if not type_check(kwarg, self.arg_type):
                    out = self._tryconv(kwarg)

        elif not type_check(out, self.arg_type):
            out = self._tryconv(out)

        if out and self.dest:
            if self.arg_nargs or self.arg_action in ("append", "append_const"):
                if self.dest not in self.env["__arguments__"]:
                    self.env["__arguments__"][self.dest] = []

                self.env["__arguments__"][self.dest].append(out)

            else:
                self.env["__arguments__"][self.dest] = out

        return out


class TaskArgParser(object):

    def __init__(self, task):

        self._parser = None
        self._dests = None

        self.task = task

        self.dargs = []
        self.oargs = []

        if task.__doc__:
            self.desc, self.long_desc = pydoc.splitdoc(task.__doc__)
        else:
            self.desc, self.long_desc = "", ""

        prog = os.path.basename(getattr(task, "_path_", task._name_))
        mgrname = self.task.parent.get_managerattr("name")

        self.prog = mgrname + " " + prog[-20:]
        self.usage = None
        self.description = self.desc
        self.epilog = ""
        self.parents = []
        self.formatter_class = argparse.RawDescriptionHelpFormatter
        self.add_help = True

    def _add_short_options(self):

        # meta argument to general options
        self.add_option_argument(
            "--general-arguments", metavar="", help="Task-common arguments. "
            "Use --verbose to see a list of general arguments")

    def _add_general_options(self):

        # general arguments
        self.add_option_argument(
            "--verbose", action="store_true", help="show long help")

        self.add_option_argument(
            "--log", metavar="log-path", type=str,
            help="activate task-level logging")

        version = ("Version is not specified." if not self.task else
                   self.task._name_ + " " + self.task._version_)
        self.add_option_argument(
            '--version', action='version', version=version,
            help="task version"
        )

        self.add_option_argument("--eval", dest="calculate", metavar="param-list",
                                 type=str, param_parse=True,
                                 action="append", help="(E,P) create a variable")
        self.add_option_argument(
            "--forward", metavar="param-list", param_parse=True, type=str,
            action="append", help="(E,P) forward variables to next task")

        self.add_option_argument(
            "--shared", metavar="param-list", param_parse=True, type=str,
            action="append", help="(E,P) make variables shared among "
            "sibling tasks in a grouptask")

#        # TODO: move assert* options to test task
#        self.add_option_argument(
#            "--assert-input", metavar="param-list", dest="assert_input",
#            type=str, param_parse=True, action="append",
#            help="(E,P) run assertion test with task input variables")
#
#        self.add_option_argument(
#            "--assert-output", metavar="param-list", dest="assert_output",
#            type=str, param_parse=True, action="append",
#            help="(E,P) run assertion test with task output variables")

        self.add_option_argument(
            "--import", metavar="module", dest="import_module", type=str,
            help="import Python module")

        self.add_option_argument(
            "--webapp", metavar="app-path", type=str,
            help="launch a web application")

        self.add_option_argument(
            "--read-pickle", metavar="path", type=str,
            help="read a pickle file")

        self.add_option_argument(
            "--write-pickle", metavar="path", type=str,
            help="write a pickle file")

        self.add_option_argument(
            "--debug", action="store_true", help="turn on debugging mode")

        # TODO: these are options for subtasks, not for grouptask
        # (0,1,2,3),x,y,z=x+y
        self.add_option_argument(
            "--send", metavar="param-list", type=str, param_parse=True,
            action="append", help="(E,P) send data to another task "
            "or a group of tasks")

        self.add_option_argument(
            "--wait", metavar="param-list", type=str, param_parse=True,
            action="append", help="(E,P) wait until all required data "
            "are arrived")

    def _add_EPmark(self, kwargs):

        help = kwargs.get("help", None)

        if help and help.lstrip().startswith("("):
            return

        evaluate = kwargs.get("evaluate", False)
        param_parse = kwargs.get("param_parse", False)

        if evaluate and param_parse:
            EPmark = "(E,P) "
        elif evaluate:
            EPmark = "(E) "
        elif param_parse:
            EPmark = "(P) "
        else:
            EPmark = ""

        if help:
            kwargs["help"] = EPmark + help
        else:
            kwargs["help"] = EPmark

    def add_data_argument(self, *vargs, **kwargs):

        self._add_EPmark(kwargs)
        self.dargs.append((vargs, kwargs))

    def del_data_argument(self, name):

        for idx in range(len(self.dargs)):
            vargs = self.dargs[idx][0]
            if vargs and vargs[0] == name:
                self.dargs.pop(idx)
                return

    def set_data_argument(self, *vargs, **kwargs):

        if not vargs:
            return

        name = vargs[0]

        self.del_data_argument(name)
        self.add_data_argument(*vargs, **kwargs)

    def add_option_argument(self, *vargs, **kwargs):
        self._add_EPmark(kwargs)
        self.oargs.append((vargs, kwargs))

    def add_verbose_help(self, typedef, action, kwargs):

        help = kwargs.get("help", "")

        # TODO: add default help
        # default = kwargs.get("default", "")
        # if default: import pdb; pdb.set_trace()

        typemsg = " (type=%s)"
        if typedef == "N/A":
            if action not in ("store_true", "store_false", "version"):
                kwargs["help"] = help + typemsg % typedef
        elif typedef is None:
            if action not in ("store_true", "store_false", "version"):
                kwargs["help"] = help + typemsg % str(str)
        else:
            kwargs["help"] = help + typemsg % str(typedef)

    def load_parser(self, argv):

        if "--verbose" in argv:
            self.description = self.long_desc
            self._add_general_options()

        elif "-h" in argv or "--help" in argv:
            self.description = self.desc
            self._add_short_options()

        else:
            self._add_general_options()

        epilog_eval = False
        epilog_param = False
        epilog = []

        if any(("evaluate" in k or k.get("help", "").startswith("(E"))
                for v, k in self.dargs):
            epilog_eval = True
            epilog.append("E: expression evaluation")

        if not epilog_eval and any(("evaluate" in k or 
                k.get("help", "").startswith("(E")) for v, k in self.oargs):
            epilog_eval = True
            epilog.append("E: expression evaluation")

        if any("param_parse" in k for v, k in self.dargs):
            epilog_param = True
            epilog.append("P: function parameter")

        if not epilog_param and any("param_parse" in k for v, k in self.oargs):
            epilog_param = True
            epilog.append("P: function parameter")

        if "--verbose" in argv:
            if epilog:
                self.epilog = "(%s)" % ", ".join(epilog)

            else:
                self.epilog = ""

        elif "-h" in argv or "--help" in argv:
            if epilog:
                self.epilog = "(%s)" % ", ".join(epilog)

        from pyloco.plxtask import PlXTask

        if isinstance(self.task, PlXTask):
            prog = os.path.basename(getattr(self.task, "_path_",
                                            self.task._name_))

            mgrname = self.task.parent.get_managerattr("name")
            self.prog = mgrname + " " + prog 

            if hasattr(self.task, "__doc__") and self.task.__doc__:
                self.desc, self.long_desc = pydoc.splitdoc(self.task.__doc__)
                self.description = self.desc

            else:
                self.description = "PlXTask"

        self._parser = _TaskArgParser(
            prog=self.prog, usage=self.usage, description=self.description,
            epilog=self.epilog, parents=self.parents,
            formatter_class=self.formatter_class, add_help=self.add_help
        )

        self._dests = []

        for vargs, kwargs in self.dargs:
            vargs = list(vargs)
            kwargs = dict(kwargs)
            evaluate = kwargs.pop("evaluate", False)
            arg_recursive = kwargs.pop("recursive", False)
            arg_type = kwargs.get("type", None)
            arg_type2 = kwargs.get("type", "N/A")
            arg_nargs = kwargs.get("nargs", None)
            arg_action = kwargs.get("action", None)
            kwargs["type"] = ArgType(arg_type, arg_action, arg_nargs,
                                     evaluate, False, self.task._env)

            if "--verbose" in argv:
                self.add_verbose_help(arg_type2, arg_action, kwargs)

            self._parser.add_argument(*vargs, **kwargs)
            dest = self._parser._actions[-1].dest
            kwargs["type"].dest = dest
            self._dests.append((dest, arg_nargs, arg_action,
                                arg_recursive))

        for vargs, kwargs in self.oargs:
            vargs = list(vargs)
            kwargs = dict(kwargs)
            evaluate = kwargs.pop("evaluate", False)
            param_parse = kwargs.pop("param_parse", False)
            arg_recursive = kwargs.pop("recursive", False)
            arg_type = kwargs.get("type", None)
            arg_type2 = kwargs.get("type", "N/A")
            arg_nargs = kwargs.get("nargs", None)
            arg_action = kwargs.get("action", "store")

            if "--verbose" in argv:
                self.add_verbose_help(arg_type2, arg_action, kwargs)

            if arg_action in ("store", "append", "store_const",
                              "append_const"):
                kwargs["type"] = ArgType(arg_type, arg_action, arg_nargs,
                                         evaluate, param_parse,
                                         self.task._env)
                try:
                    self._parser.add_argument(*vargs, **kwargs)
                except:
                    print("BBB", vargs, kwargs)
                    #import pdb; pdb.set_trace()
                dest = self._parser._actions[-1].dest
                kwargs["type"].dest = dest

            else:
                self._parser.add_argument(*vargs, **kwargs)
                dest = self._parser._actions[-1].dest

            self._dests.append((dest, arg_nargs, arg_action,
                                arg_recursive))

    def generate_help(self, argv):

        if self._parser is None:
            self.load_parser(argv)

        if self.task._fwddefs:
            group = self._parser.add_argument_group(
                    'forward output variables')

            for dest, (type, help) in self.task._fwddefs.items():
                kwargs = {"help": help}

                if "--verbose" in argv:
                    if type is None:
                        self.add_verbose_help("N/A", "store", kwargs)

                    else:
                        self.add_verbose_help(type, "store", kwargs)

                group.add_argument("$%s$" % dest, **kwargs)

        if self.task._shrdefs:
            group = self._parser.add_argument_group(
                    'shared output variables')

            for dest, (type, help) in self.task._shrdefs.items():
                kwargs = {"help": help}

                if "--verbose" in argv:
                    if type is None:
                        self.add_verbose_help("N/A", "store", kwargs)

                    else:
                        self.add_verbose_help(type, "store", kwargs)

                group.add_argument("$%s$" % dest, help=help)

        usage_str = self._parser.format_usage()
        remained_str = self._parser.format_help()[len(usage_str):]

        usage = _re_dest.sub("", usage_str)
        remained = remained_str.replace("$", " ").rstrip()

        return usage, remained

    def parse_args(self, argv, fpenv, parse_known_args=False, reload_parser=False):

        if reload_parser:
            self._parser = None

        if self._parser is None:
            self.load_parser(argv)

        if any([(opt in argv) for opt in ("-h", "--help", "--verbose")]):
            usage, remained = self.generate_help(argv)
            print(usage, remained)
            raise NormalExit()

        unknown_args = []

        # parse with argv
        if parse_known_args:
            args, unknown_args = self._parser.parse_known_args(argv)

        else:
            args = self._parser.parse_args(argv)

        # TODO param_parse support???
        clsname = self.task.__class__.__name__

        for dest, nargs, action, arg_recursive in self._dests:

            if not hasattr(args, dest) or getattr(args, dest) is None:
                if dest in fpenv:
                    if nargs or action in ("append", "append_const"):
                        if dest not in self.task._env["__arguments__"]:
                            self.task._env["__arguments__"][dest] = []

                        self.task._env["__arguments__"][dest].append(fpenv[dest])

                    else:
                        self.task._env["__arguments__"][dest] = fpenv[dest]

                    setattr(args, dest, fpenv[dest])

                elif arg_recursive and dest in self.task._fwds:
                    # TODO: add __arguments__??
                    setattr(args, dest, self.task._fwds[dest])

                elif self._parser.pos_required.get(dest, False):
                    raise UsageError("missing required argument at %s: '%s'" %
                                     (clsname, dest))

            elif ((nargs in ("*", "+") or isinstance(nargs, int) or
                    action in ("append", "append_const")) and
                    getattr(args, dest) == []):
                if dest in fpenv:
                    if dest not in self.task._env["__arguments__"]:
                        self.task._env["__arguments__"][dest] = []

                    self.task._env["__arguments__"][dest].append(fpenv[dest])

                    setattr(args, dest, [fpenv[dest]])

                elif arg_recursive and dest in self.task._fwds:
                    setattr(args, dest, [self.task._fwds[dest]])

                elif self._parser.pos_required.get(dest, False):
                    raise UsageError("missing required argument at %s: '%s'" %
                                     (clsname,dest))

            elif (((nargs in ("*", "+") or isinstance(nargs, int)) and
                    action in ("append", "append_const")) and
                    getattr(args, dest) == [[]]):
                if dest in fpenv:
                    if dest not in self.task._env["__arguments__"]:
                        self.task._env["__arguments__"][dest] = []

                    self.task._env["__arguments__"][dest].append([fpenv[dest]])

                    setattr(args, dest, [[fpenv[dest]]])

                elif arg_recursive and dest in self.task._fwds:
                    setattr(args, dest, [[self.task._fwds[dest]]])

                elif self._parser.pos_required.get(dest, False):
                    raise UsageError("missing required argument at %s: '%s'" %
                                     (clsname, dest))

        return args, unknown_args


class TestArgParser(TaskArgParser):

    def __init__(self, task):

        super(TestArgParser, self).__init__(task)

        self.add_option_argument(
            "--assert-input", metavar="param-list", dest="assert_input",
            type=str, param_parse=True, action="append",
            help="(E,P) run assertion test with task input variables")

        self.add_option_argument(
            "--assert-output", metavar="param-list", dest="assert_output",
            type=str, param_parse=True, action="append",
            help="(E,P) run assertion test with task output variables")


class GroupCmdArgParser(TaskArgParser):

    def __init__(self, task):

        super(GroupCmdArgParser, self).__init__(task)

        # TODO: add verbose_help argument??

        # TODO: add param_parse
        self.add_option_argument(
            "--arrange", metavar="param-list", type=str, default="column",
            help="arrange connections of sub-tasks")

        #self.add_option_argument(
        #    "--reduce", metavar="param-list", type=str, param_parse=True,
        #    action="append", help="(E,P) copying data from sub-tasks "
        #    "and forward it to next task")

        self.add_option_argument(
            "--repeat", metavar="param-list", type=str, param_parse=True,
            help="(E,P) repeat sub-tasks")
