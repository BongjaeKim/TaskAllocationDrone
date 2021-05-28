# -*- coding: utf-8 -*-
"""standard task module."""

from __future__ import unicode_literals

import os
from typing import List

from pyloco.helptask import HelpTask
from pyloco.grouptask import GroupCmdTask
from pyloco.parse import GroupCmdArgParser
from pyloco.task import StandardTask, load_taskclass
from pyloco.util import (pyloco_print, pyloco_formatter, pyloco_input,
                         StringIO)

class InputTask(StandardTask):
    """read user input

'input' task takes string input, possibily interactively. Its main usage is
to accept user input and to forward it to other tasks. Using '--calc'
option, user can generate a new variable from Python expression.
"""

    _version_ = "0.1.0"
    _name_ = "input"

    def __init__(self, parent):

        self.add_data_argument("data", nargs="*", required=False, type=str,
                               help="input data")

        self.add_option_argument("-i", "--interactive", action="store_true",
                                 help="interactive user input")
        self.add_option_argument("-p", "--prompt", default=">>> ",
                                 help="command prompt")

        #self._input_dargs = [d[0] for d in self._parser.dargs]
        #self._input_oargs = [o[0] for o in self._parser.oargs]

        self.register_forward("data", type=List[str],
                              help="forward input data")

    def _eval(self, opt):

        for expr in opt.vargs:
            eval(expr, self._env)

        for lhs, rhs in opt.kwargs.items():
            self._env[lhs] = eval(rhs, self._env)

    def perform(self, targs):

        data = targs.data

        if targs.interactive:
            data = [pyloco_input(targs.prompt)]

        #if targs.calc:
        #    for calc in targs.calc:
        #        self._eval(calc)

        self.add_forward(data=data)

        return 0


class GroupInputCmdTask(GroupCmdTask, InputTask):

    def __init__(self, parent):

        super(GroupInputCmdTask, self).__init__(parent)
        InputTask.__init__(self, parent)

    def perform(self, targs):

        retval = InputTask.perform(self, targs)

        if retval is None:
            retval = 0

        InputTask.post_perform(self, targs)
        self._data = self._fwds
        self._fwds = {}

        return super(GroupInputCmdTask, self).perform(targs)


class PrintTask(StandardTask):
    """display input text

'print' task displays input text on screen. Its main usage is to print
data forwarded from previous task(s).
"""

    _version_ = "0.1.0"
    _name_ = "print"

    def __init__(self, parent):

        self.add_data_argument("data", nargs="*", help="input text to print")

        self.add_option_argument("--evaluate", dest="evaluate", action="store_true", help="evaluate input")
        self.add_option_argument("-n", "--no-newline", action="store_true",
                                 help="remove newline")

        self.register_forward("stdout", type=str, help="standard output")

    def perform(self, targs):

        end = "" if targs.no_newline else "\n"

        if targs.data:
            l = []

            for d in targs.data:
                if isinstance(d, str):
                    fmt = pyloco_formatter.vformat(str(d), [], self._env)
                    if targs.evaluate:
                        l.append(str(eval(fmt)))
                    else:
                        l.append(fmt)
                else:
                    l.append(str(d))

            out = " ".join(l)
            pyloco_print(out, end=end)
            stdout = out + end
        else:
            stdout = "No data to print."
            pyloco_print(stdout)

        self.add_forward(stdout=stdout)


standard_tasks = {
        "help":             HelpTask,
        "input":            InputTask,
        "print":            PrintTask,
    }
