# -*- coding: utf-8 -*-
"""plx module."""

from __future__ import unicode_literals

import os
import re
import pydoc

from pyloco.task import Task
from pyloco.error import UsageError
from pyloco.util import parse_param_option, pyloco_formatter, system, pyloco_import
from pyloco.base import pyloco_builtins

_pat_section = r"^\s*\[(?P<sec>.+)\]\s*\Z"
_pat_attr_section = r"^attribute\s*\*\Z"
_pat_comment = r"^\s*#"
_pat_continue = r".*\\\s*\Z"
_pat_ident = r"(?P<ident>[^\d\W]\w*)"
_pat_id = r"[^\d\W]\w*"

_re_section = re.compile(_pat_section)
_re_attr_section = re.compile(_pat_attr_section)
_re_comment = re.compile(_pat_comment)
_re_continue = re.compile(_pat_continue)
# _re_ident = re.compile(_pat_ident)
_re_plxcmd = re.compile(r"^[^@]+(@\s*"+_pat_id+r"\s*)+\s*=")


def read_plx(path):

    entry_section = ("__entry__", [])
    attr_section = ("attribute*", [])
    section = entry_section
    plx_sections = []

    with open(path) as fplx:
        contflag = False
        item = ""

        for line in fplx.read().splitlines():
            if _re_comment.match(line):
                contflag = False
                item = ""
                continue

            if contflag:
                contflag = False

            if _re_continue.match(line):
                item += line.rstrip()[:-1]
                contflag = True
                continue

            item += line

            if item:
                match = _re_section.match(item)
                if match:
                    header = match.group("sec")
                    section = (header.strip(), [])

                    if _re_attr_section.match(section[0]):
                        attr_section = section

                    else:
                        plx_sections.append(section)

                else:
                    section[1].append(item)

                item = ""
            else:
                section[1].append(item)

    return entry_section, attr_section, plx_sections


def collect_plx_command(item):

    line = None
    plx_cmd = None

    match = _re_plxcmd.match(item)
    if match:
        args = item[:match.span()[1]-1]
        opt = parse_param_option(args, False, None)
        plx_cmd = (opt, item[match.span()[1]:])

    else:
        line = item

    return plx_cmd, line


class PlXTask(Task):
    """PlX task

PlX task merges the strengths of Python, Shell script,
and INI file syntax
"""

    _version_ = "0.1.0"

    def _setup(self, taskpath):

        self.plx_entry_section, self.plx_attr_section, self.plx_sections = \
            read_plx(taskpath)

        self.plx_entry_body, self.plx_argdefs, self.plx_fwddefs, \
            self.plx_shrdefs = [], {}, {}, {}

        self._env["__file__"] = os.path.abspath(taskpath)

        for line in self.plx_entry_section[1]:

            _match, _line = collect_plx_command(line)

            if _match:
                opt = _match[0]
                name = opt.vargs[0]
                ctx = opt.context[0]
                if ctx == "arg":
                    rhs = parse_param_option(_match[1], True, None)
                    self.plx_argdefs[name] = rhs
                elif ctx == "forward":
                    rhs = parse_param_option(_match[1], True, None)
                    self.plx_fwddefs[name] = rhs
                elif ctx == "shared":
                    rhs = parse_param_option(_match[1], True, None)
                    self.plx_shrdefs[name] = rhs
                else:
                    self.plx_entry_body.append(line)

            if _line is not None:
                self.plx_entry_body.append(_line)

        for opt in self.plx_argdefs.values():
            if opt.vargs:
                if opt.vargs[0].startswith("-"):
                    self.add_option_argument(*opt.vargs, **opt.kwargs)
                else:
                    self.add_data_argument(*opt.vargs, **opt.kwargs)

        for fwd in self.plx_fwddefs.values():
            self.register_forward(*fwd.vargs, **fwd.kwargs)

        for shr in self.plx_shrdefs.values():
            self.add_shared(*opt.vargs, **opt.kwargs)

        self._section_handlers = {
                "forward": self.run_forward_section,
                "shared": self.run_shared_section,
            }

        self._command_handlers = {
                "shell": self.run_shell_command,
                "manager": self.run_manager_command,
            }

        lenv = {}
        if self.plx_attr_section:
            self.run_section(self.plx_attr_section[1], lenv=lenv)
            for key, value in lenv.items():
                if key in ("_doc_",):
                    setattr(self, "_%s_" % key, value)

                setattr(self, key, value)

        if "_name_" not in lenv:
            _, self._name_ = os.path.split(taskpath)

    def run(self, argv, subargv=None, forward=None):

        if not argv:
            raise UsageError("PlX Task is not found."
                             " Please check plx path.")

        elif not os.path.isfile(argv[0]):
            raise UsageError("PlX Task '%s' is not found."
                             " Please check plx path." % str(argv[0]))

        self._setup(argv[0])

        prog = os.path.basename(getattr(self, "_path_", self._name_))
        self._parser.prog = self.get_mgrname() + " " + prog[-20:]

        if hasattr(self, "__doc__") and self.__doc__:
            self._parser.desc, self._parser.long_desc = pydoc.splitdoc(
                                                        self.__doc__)

        return super(PlXTask, self).run(argv[1:], subargv=subargv,
                                        forward=forward)

    def perform(self, targs):

        for plx_dest, opt in self.plx_argdefs.items():
            dest = opt.kwargs.get("dest", opt.vargs[0])
            if dest in self._env["__arguments__"]:
                argval = self._env["__arguments__"].pop(dest, None)
                self._env["__arguments__"][plx_dest] = argval

        out = self.run_section(self.plx_entry_body)

        if out == 0:
            for hdr, body in self.plx_sections:
                # check hdr
                if hdr.endswith("*"):
                    special_sec = True
                    opt = parse_param_option(hdr[:-1], False,
                                             self.parent.shared)
                else:
                    special_sec = False
                    opt = parse_param_option(hdr, False, self.parent.shared)

                env = dict(self.parent.shared)
                env["__builtins__"] = pyloco_builtins
                sec_check = all([eval(c, env) for c in opt.context])

                if sec_check:
                    sec_name = opt.vargs[0]

                    # find sec_handler
                    if special_sec:
                        if sec_name in self._section_handlers:
                            sec_handler = self._section_handlers[sec_name]

                        else:
                            raise UsageError(
                                "Special section '%s' is not registered."
                                " Please register first." % sec_name
                            )
                    else:
                        sec_handler = self.run_section

                    out = sec_handler(body, *opt.vargs[1:], **opt.kwargs)

        return out

    def run_section(self, body, *vargs, **kwargs):

        env = dict(self._env)
        env.update(self.parent.shared)
        lenv = kwargs.get("lenv", {})

        lines = []
        hidx = 0

        for b in body:
            l1 = b.replace("{", "{{").replace("}", "}}")
            l2 = l1.replace("__{{", "{").replace("}}__", "}")
            l3 = pyloco_formatter.vformat(l2, [], env)

            _match, _line = collect_plx_command(l3)

            if _match:
                opt = _match[0]
                name = opt.vargs[0]
                cmd_handler = None

                for ctx in opt.context:
                    if ctx in self._command_handlers:
                        cmd_handler = self._command_handlers[ctx]
                        break
                    # rhs = parse_param_option(_match[1], True, None)

                if cmd_handler:
                    idx_space = l3.find(name)
                    fname = "__plx_cmd_handler%d__" % hidx
                    hidx += 1
                    env[fname] = cmd_handler
                    vargs = ", ".join(opt.vargs[1:])
                    kwargs = ", ".join(["%s=%s" % (k, v) for k, v in
                                       opt.kwargs.items()])

                    if kwargs:
                        args = "%s, %s" % (vargs, kwargs)

                    else:
                        args = vargs

                    cmd = (_match[1].replace('\\"', '__EDQ__')
                           .replace('"', '\\"').replace('__EDQ__', '\\\\\\"'))

                    cmd = cmd.strip()

                    if args:
                        lines.append(l3[:idx_space] + "%s = " % name + fname +
                                     '("%s", %s)' % (cmd, args))
                    else:
                        lines.append(l3[:idx_space] + "%s = " % name + fname +
                                     '("%s")' % cmd)
                else:
                    raise UsageError("command handler for '%s' is not found." %
                                     opt.context[0])
            else:
                lines.append(l3)

        exec("\n".join(lines), env, lenv)
        self.parent.shared.update(lenv)

        return lenv["out"][0] if "out" in lenv else 0

    def run_forward_section(self, body, *vargs, **kwargs):
        lenv = {}
        if self.run_section(body, lenv=lenv) == 0:
            fwds = {}
            for fwd, opt in self.plx_fwddefs.items():
                if fwd in lenv:
                    fwds[opt.vargs[0]] = lenv[fwd]
            self.add_forward(**fwds)
            return 0
        return -1

    def run_shared_section(self, body, *vargs, **kwargs):
        lenv = {}
        if self.run_section(body, lenv=lenv) == 0:
            shrs = {}
            for shr, opt in self.plx_shrdefs.items():
                if shr in lenv:
                    shrs[opt.vargs[0]] = lenv[shr]
            self.add_shared(**shrs)
            return 0
        return -1

    def run_shell_command(self, cmd, *vargs, **kwargs):

        return system(cmd)

    def run_manager_command(self, cmd, *vargs, **kwargs):

        mgr = pyloco_import(self.get_mgrname())

        if not cmd:
            return (-1, None)

        if cmd.startswith("-"):
            if cmd.startswith("-- "):
                return mgr.perform("", "", cmd[3:])
            else:
                idx = cmd.find("-- ")
                if idx > 0:
                    return mgr.perform("", cmd[:idx], cmd[idx+3:])
                else:
                    return mgr.perform("", cmd)
        else:
            return mgr.perform("", "", cmd)

