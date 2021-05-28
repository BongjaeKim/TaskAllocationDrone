# -*- coding: utf-8 -*-
"""utility module."""

from __future__ import unicode_literals, print_function

import sys
import os
import re
import subprocess
import tempfile
import shutil
import string
import ast
import time
import inspect
import typing
import socket
import pickle
import pickletools

from pyloco.error import UsageError

PY3 = sys.version_info >= (3, 0)

if sys.platform in ("linux", "linux2"):
    OS = "linux"
elif sys.platform == "darwin":
    OS = "osx"
elif sys.platform == "win32":
    OS = "windows"

if PY3:

    from importlib import __import__ as pyloco_import

    from urllib.request import urlopen
    from urllib.parse import urlparse
    from urllib.error import HTTPError, URLError

    from http.server import HTTPServer, BaseHTTPRequestHandler
    from http.client import HTTPConnection

    from io import StringIO, BytesIO

    def pyloco_print(msg, **kwargs):

        if type(msg) == type(b"a"):     # noqa: E721
            print(msg.decode("utf-8"), **kwargs)

        else:
            print(msg, **kwargs)

    def pyloco_mp_get_context(method):

        import multiprocessing
        multiprocessing.get_context(method)

    import shlex as pyloco_shlex

    pyloco_input = input

else:

    pyloco_import = __import__

    from urllib2 import urlopen, HTTPError, URLError    # noqa: F401
    from urlparse import urlparse                       # noqa: F401

    from BaseHTTPServer import HTTPServer               # noqa: F401
    from BaseHTTPServer import BaseHTTPRequestHandler   # noqa: F401
    from httplib import HTTPConnection                  # noqa: F401

    from StringIO import StringIO                       # noqa: F401
    from cStringIO import StringIO as BytesIO           # noqa: F401

    def pyloco_print(msg, **kwargs):

        if "end" in kwargs:
            msg = msg + kwargs["end"]

        else:
            msg = msg + "\n"

        if type(msg) == type(u"A"):     # noqa: E721
            sys.stdout.write(msg.encode("utf-8"))

        else:
            sys.stdout.write(msg)

    def pyloco_mp_get_context(method):
        pass

    import ushlex as pyloco_shlex

    pyloco_input = raw_input    # noqa: F821


_pat_field = r"^\s*(?P<first>[^\d\W]\w*)\s*(?P<rest>.*)$"
_re_field = re.compile(_pat_field)

def which(program):

    def is_exe(fpath):

        return (os.path.exists(fpath) and os.access(fpath, os.X_OK) and
                os.path.isfile(fpath))

    def ext_candidates(fpath):

        yield fpath

        for ext in os.environ.get("PATHEXT", "").split(os.pathsep):
            yield fpath + ext

    fpath, fname = os.path.split(program)

    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)

            for candidate in ext_candidates(exe_file):
                if is_exe(candidate):
                    return candidate
    return None

# to unicode
def strdecode(string, encoding=None):

    outstr = string

    if type(string) != type(u"A"):  # noqa: E721
        try:
            if encoding is not None:
                outstr = outstr.decode(encoding)

            elif sys.stdout.encoding:
                outstr = outstr.decode(sys.stdout.encoding)

            else:
                outstr = outstr.decode("utf-8")

        except Exception:
            pass

    return outstr


# to utf-8
def strencode(string, encoding=None):

    outstr = string

    if type(string) == type(u"A"):      # noqa: E721
        try:
            if encoding is not None:
                outstr = outstr.encode(encoding)

            else:
                outstr = outstr.encode("utf-8")

        except Exception:
            pass

    return outstr


def system(cmd, **kwargs):

    if OS == "windows":
        kwargs["shell"] = True
        if isinstance(cmd, (tuple, list)):
            cmd = " ".join(cmd)
    else:
        if not isinstance(cmd, (tuple, list)):
            cmd = pyloco_shlex.split(cmd)

    tmpout = False
    tmperr = False

    stdout = kwargs.pop("stdout", None)
    stderr = kwargs.pop("stderr", None)

    if stdout is None:
        stdout = tempfile.TemporaryFile()
        tmpout = True

    if stderr is None:
        stderr = tempfile.TemporaryFile()
        tmperr = True

    popen = subprocess.Popen(cmd, stdout=stdout, stderr=stderr,
                             **kwargs)

    retval = popen.wait()

    if tmpout:
        stdout.seek(0)
        out = strdecode(stdout.read())
        stdout.close()

    else:
        out = stdout

    if tmperr:
        stderr.seek(0)
        err = strdecode(stderr.read())
        stderr.close()

    else:
        err = stderr

    return retval, out, err


def isystem(cmd, **kwargs):

    if OS == "windows":
        kwargs["shell"] = True

        if isinstance(cmd, (tuple, list)):
            cmd = " ".join(cmd)
    else:
        if not isinstance(cmd, (tuple, list)):
            cmd = pyloco_shlex.split(cmd)

    kwargs.pop("stdout", None)
    kwargs.pop("stderr", None)

    p = subprocess.Popen(cmd, stderr=subprocess.PIPE)

    while True:

        out = p.stderr.read(1)
        # if out == '' and p.poll() is not None:
        if out == '' or p.poll() is not None:
            break

        if out != '':
            if PY3:
                sys.stdout.write(out.decode("utf-8"))

            else:
                sys.stdout.write(out)

            sys.stdout.flush()

    retval = p.wait()

    return retval


def load_pymod(head, base):

    sys.path.insert(0, os.path.abspath(os.path.realpath(head)))

    m = pyloco_import(base)
    sys.path.pop(0)
    return m


class PylocoFormatter(string.Formatter):

    def vformat(self, format_string, args, kwargs):

        if "__format__" not in kwargs:
            kwargs["__format__"] = {}

        out = super(PylocoFormatter, self).vformat(
            format_string, args, kwargs)

        return out if PY3 else out[0]

    def convert_field(self, obj, conversion):

        return super(PylocoFormatter, self).convert_field(obj, conversion)

    def pyloco_get_field(self, field_name, conversion, format_spec,
                         args, kwargs):

        match = _re_field.match(field_name)
        first = match.group("first")
        rest = match.group("rest").strip()

        if format_spec == "arg":
            if first in kwargs["__arguments__"]:
                obj = kwargs["__arguments__"][first]
            else:
                return "", first

        elif format_spec == "clone":
            obj = eval(self.get_value(first, args, kwargs), kwargs)

        else:
            obj = self.get_value(first, args, kwargs)

        if rest:
            obj = eval("__tmpval__"+rest, kwargs, {"__tmpval__": obj})

        obj = self.convert_field(obj, conversion)

        # handle formatting
        if format_spec in ("arg", "clone"):
            pass

        else:
            obj = self.format_field(obj, format_spec)

        return obj, first

    def _vformat(self, format_string, args, kwargs, used_args, recursion_depth,
                 auto_arg_index=0):

        if recursion_depth < 0:
            raise ValueError('Max string recursion exceeded')

        result = []

        for literal_text, field_name, format_spec, conversion in \
                self.parse(format_string):

            fmtname = "fmt%d" % len(kwargs["__format__"])
            result.append(literal_text)

            # if there's a field, output it
            if field_name is not None:
                # handle arg indexing when empty field_names are given.

                if field_name == '':
                    if auto_arg_index is False:
                        raise ValueError('cannot switch from manual field '
                                         'specification to automatic field '
                                         'numbering')
                    field_name = str(auto_arg_index)
                    auto_arg_index += 1
                elif field_name.isdigit():
                    if auto_arg_index:
                        raise ValueError('cannot switch from manual field '
                                         'specification to automatic field '
                                         'numbering')
                    # disable auto arg incrementing, if it gets
                    # used later on, then an exception will be raised
                    auto_arg_index = False

                # expand the format spec, if needed
                format_spec, auto_arg_index = self._vformat(
                    format_spec, args, kwargs,
                    used_args, recursion_depth-1,
                    auto_arg_index=auto_arg_index)

                # given the field_name, find the object it references
                #  and the argument it came from

                # format the object and append to the result
                if "__defer__" in kwargs and kwargs["__defer__"]:
                    kwargs["__format__"][fmtname] = (
                        self.pyloco_get_field, field_name, conversion,
                        format_spec
                    )
                    result.append("__format__['%s'][0](__format__['%s'][1],"
                                  "__format__['%s'][2], __format__['%s'][3],"
                                  "[], globals())[0]" % (
                                      fmtname, fmtname, fmtname, fmtname)
                                  )
                else:
                    obj, arg_used = self.pyloco_get_field(
                        field_name, conversion, format_spec, args, kwargs)
                    result.append(obj)
                    used_args.add(arg_used)
                    #kwargs["__format__"][fmtname] = obj
                    #print("TTT", fmtname, obj)
                    #result.append("__format__['%s']" % fmtname)

        return ''.join(result), auto_arg_index


pyloco_formatter = PylocoFormatter()


def teval(expr, env, **kwargs):

    retval = None

    if not env:
        from pyloco.base import pyloco_builtins
        env = {"__builtins__": pyloco_builtins}

    if "__builtins__" not in env:
        from pyloco.base import pyloco_builtins
        env["__builtins__"] = pyloco_builtins

    if type(expr) == type(u"A"):    # noqa: E721
        retval = eval(expr, env, kwargs)

    elif isinstance(expr, list):
        retval = []

        for _e in expr:
            retval.append(eval(_e, env, kwargs))

    elif isinstance(expr, dict):
        retval = {}

        for k, _e in expr.items():
            retval[k] = eval(_e, env, kwargs)

    return retval


class Option(object):

    def __init__(self, *vargs, **kwargs):

        self.context = kwargs.pop("context", [])
        self.vargs = list(vargs)
        self.kwargs = kwargs

    def __str__(self):

        out = []
        ctx = []

        for v in self.vargs:
            out.append(str(v))

        for k, v in self.kwargs.items():
            out.append(k+"="+str(v))

        for c in self.context:
            ctx.append("@" + c)

        return ",".join(out) + "".join(ctx)


def parse_literal_args(expr):

    lv = []
    lk = {}

    expr_items = expr.split(",")
    text = ""

    while expr_items:

        expr_item = expr_items.pop(0).strip()

        if not expr_item:
            continue

        if text:
            text = text + "," + expr_item

        else:
            text = expr_item

        #if not text:
        #    continue

        try:
            tree = ast.parse("func({0})".format(text))
            args = tree.body[0].value.args
            keywords = tree.body[0].value.keywords

            if len(args) > 0 and len(keywords):
                raise UsageError("Both of args and keywords are found"
                                 " during argument parsing.")
            text = text.strip()

            if not text:
                continue

            if len(args) > 0:
                lv.append(text)

            elif len(keywords) > 0:
                key, val = text.split("=", 1)

                if val:
                    lk[key] = val

            text = ""

        except Exception:
            pass

    #if not lv and not lk:
    #    lv.append(expr)

    return lv, lk


def is_valid_variable_name(name):
    try:
        ast.parse("{} = None".format(name))
        return True

    except:
        return False

def parse_param_option(val, evaluate, env):

    def _p(*argv, **kw_str):
        return list(argv), kw_str

    obj = Option()

    if isinstance(val, str) or type(val) == type(u"A"):  # noqa: E721
        items = [v.strip() for v in val.split("@")]
        obj.context = items[1:]

        for c in obj.context:
            if not is_valid_variable_name(c):
                items = [val]
                obj.context = []
                break

        if evaluate:
            eval_out = teval('_p({0})'.format(items[0]), env, _p=_p)

            if eval_out:
                obj.vargs, obj.kwargs = eval_out

            else:
                raise UsageError("syntax error at '{0}'."
                                 .format(items[0]))
        else:
            obj.vargs, obj.kwargs = parse_literal_args(items[0])
    else:
        obj.vargs = [val]

    return obj


def iterpath(path):

    if os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith(".py"):
                    yield os.path.join(dirpath, filename)

    elif path.endswith(".py"):
        yield path

    else:
        iter([])


class create_tempdir(object):

    def __new__(cls, context=False):

        if context:
            return super(create_tempdir, cls).__new__(cls)

        else:
            return tempfile.mkdtemp()

    def __enter__(self):

        self.name = tempfile.mkdtemp()
        return self.name

    def __exit__(self, exc_type, exc_value, traceback):

        shutil.rmtree(self.name)


def is_venv():

    return (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix')
            and sys.base_prefix != sys.prefix))


def get_pip():

    if "CONDA_DEFAULT_ENV" in os.environ:
        return "pip"

    pyver = sys.version_info

    pipname = "pip%d.%d" % (pyver.major, pyver.minor)
    if which(pipname):
        return pipname

    pipname = "pip%d" % pyver.major
    if which(pipname):
        return pipname

    pipname = "pip"
    if which(pipname):
        return pipname

    print("Could not find 'pip' Python package manager.")
    sys.exit(-1)


def split_assert_expr(expr):

    seperators = ["==", "!=", "is", "is not", "in",
                  "not in", ">", ">=", "<", "<="]

    # assertEqual(a, b)      a == b
    # assertNotEqual(a, b)	a != b
    # assertIs(a, b)         a is b
    # assertIsNot(a, b)      a is not b
    # assertIn(a, b)         a in b
    # assertNotIn(a, b)      a not in b
    # assertGreater(a, b)    a > b
    # assertGreaterEqual(a, b)   a >= b
    # assertLess(a, b)       a < b
    # assertLessEqual(a, b)  a <= b

    # assertIsInstance(a, b)	isinstance(a, b)
    # assertNotIsInstance(a, b)	not isinstance(a, b)
    # assertRaises(exc, fun, *args, **kwds)	fun(*args, **kwds) raises exc
    # assertRaisesRegex(exc, r, fun, *args, **kwds)	fun(*args, **kwds)
    #                              raises exc and the message matches regex r
    # assertWarns(warn, fun, *args, **kwds)	fun(*args, **kwds) raises warn
    # assertWarnsRegex(warn, r, fun, *args, **kwds)	fun(*args, **kwds)
    #                          raises warn and the message matches regex r
    # assertLogs(logger, level)	The with block logs on logger with minimum
    #                           level
    # assertAlmostEqual(a, b)	round(a-b, 7) == 0
    # assertNotAlmostEqual(a, b)	round(a-b, 7) != 0
    # assertRegex(s, r)	r.search(s)
    # assertNotRegex(s, r)	not r.search(s)
    # assertCountEqual(a, b)	a and b have the same elements in the same
    #                           number, regardless of their order.
    # assertMultiLineEqual(a, b)	strings
    # assertSequenceEqual(a, b)	sequences
    # assertListEqual(a, b)	lists
    # assertTupleEqual(a, b)	tuples
    # assertSetEqual(a, b)	sets or frozensets
    # assertDictEqual(a, b)	dicts

    expr_pairs = {}

    for sep in seperators:

        expr_items = expr.split(sep)
        lexpr = ""

        while expr_items:

            if lexpr:
                lexpr = lexpr + sep + expr_items.pop(0)

            else:
                lexpr = expr_items.pop(0)

            if not lexpr or not expr_items:
                break

            try:
                ast.parse(lexpr)
                rexpr = sep.join(expr_items).lstrip()
                ast.parse(rexpr)
                expr_pairs[sep] = (lexpr.rstrip(), rexpr.rstrip())
                break

            except Exception:
                pass

    return expr_pairs

# # Concrete collection types.
# 'Counter',
# 'Deque',
# 'Dict',
# 'DefaultDict',
# 'List',
# 'Set',
# 'FrozenSet',
# 'NamedTuple',  # Not really a type.
# 'Generator',

# Special typing constructs Union, Optional, Generic, Callable and Tuple
# use three special attributes for internal bookkeeping of generic types:
# * __parameters__ is a tuple of unique free type parameters of a generic
#   type, for example, Dict[T, T].__parameters__ == (T,);
# * __origin__ keeps a reference to a type that was subscripted,
#   e.g., Union[T, int].__origin__ == Union;
# * __args__ is a tuple of all arguments used in subscripting,
#   e.g., Dict[T, int].__args__ == (T, int).


def type_check(obj, _type):

    if isinstance(obj, Option):
        for arg in obj.vargs + list(obj.kwargs.values()):
            if not type_check(arg, _type):
                return False
        _type = None

    elif _type == str and not PY3:
        return (isinstance(obj, _type) or
                type_check(obj, unicode))   # noqa: F821

    if _type is not None:
        try:

            if not isinstance(obj, _type):
                return False

            if issubclass(_type, typing.Container):
                if hasattr(_type, "__args__"):
                    if issubclass(_type, typing.List):
                        args = _type.__args__[0]
                        for item in obj:
                            type_check(item, args)

                    elif issubclass(_type, typing.Tuple):
                        for item, _t in zip(obj, _type.__args__):
                            type_check(item, _t)

                    elif issubclass(_type, typing.Dict):
                        import pdb; pdb.set_trace()     # noqa: E702

        except TypeError:
            origin = getattr(_type, "__origin__", None)

            if origin is None or not isinstance(obj, origin):
                return False

    return True


def get_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    host, port = sock.getsockname()
    sock.close()
    return port


def pack_websocket_message(sender, msgtype, body):

    return {"time": time.time(), "sender": sender,  "type": msgtype,
            "body": body}


def _place_holder():

    class dummy():
        pass

    obj = dummy()
    return obj

def is_ipv6():
    try:
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        return True
    except:
        return False

def split_docsection(text):

    long_desc = None
    sections = []
    lines = text.split("\n")
    preidx = 0
    idx = 0

    for idx, (lprev, lnext) in enumerate(zip(lines[:-1], lines[1:])):
        n = lnext.lstrip() 

        if not n or n[0].isalnum() or any(c != n[0] for c in n[1:]):
            continue

        p = lprev.lstrip()
        if len(p) > len(n):
            continue

        if long_desc is not None:
            sections.append("\n".join(lines[preidx:idx]).rstrip() + "\n")
        elif idx > 0:
            long_desc = lines[preidx:idx]
        else:
            long_desc = []

        preidx = idx

    if preidx != idx:
        if long_desc is None:
            long_desc = lines[preidx:idx+2]

        else:
            sections.append("\n".join(lines[preidx:idx+2]).rstrip() + "\n")

    elif preidx == 0:
        long_desc = [text]

    else:
        sections.append("\n".join(lines[preidx:idx+2]).rstrip() + "\n")

    return "\n".join(long_desc).rstrip(), sections

def is_pickle(data):

    try:
        for idx, _ in enumerate(pickletools.genops(data)):
            if idx > 100:
                break
        return True

    except Exception:
        return False


class PylocoPickle(object):

    def __init__(self):

        self._readers = {}
        self._ndata = 0
        self.tempdir = tempfile.mkdtemp()

    def dump(self, data, path):

        with open(os.path.join(self.tempdir, "data"), 'wb') as f:

            pickle.dump(data, f, protocol=2)

        with open(os.path.join(self.tempdir, "reader"), 'wb') as f:
            readers = {}

            for reader, key in self._readers.items():
                lines = inspect.getsource(reader).split("\n")
                nsp = len(lines[0]) - len(lines[0].lstrip())
                readers[key] = "\n".join([l[nsp:] for l in lines])

            pickle.dump(readers, f, protocol=2)

        zipname = shutil.make_archive(path, 'zip', self.tempdir)
        shutil.move(zipname, path)
        shutil.rmtree(self.tempdir)

    def _recover(self, data):

        for key, value in data.items():
            sentinel_pyloco = "__pyloco__"

            if key.startswith(sentinel_pyloco):
                import pdb; pdb.set_trace()

            elif isinstance(value, dict):
                data[key] = self._recover(value)

        return data

    def load(self, path):

        shutil.unpack_archive(path, self.tempdir, "zip")

        with open(os.path.join(self.tempdir, "reader"), 'rb') as f:
            for key, src in pickle.load(f):
                import pdb; pdb.set_trace()

        with open(os.path.join(self.tempdir, "data"), 'rb') as f:
            data = self._recover(pickle.load(f))

        shutil.rmtree(self.tempdir)

        return data

    def attach_reader(self, reader):

        ndata = str(self._ndata)
        path = os.path.join(self.tempdir, ndata)

        if reader in self._readers:
            key = self._readers[reader]

        else:
            key = str(len(self._readers))
            self._readers[reader] = key

        return path, "__pyloco__file__" + key + "__" + ndata

def import_modulepath(path):

    #debug(path == "test.plx")

    fragment = None
    spath = [p.strip() for p in path.split("#")]

    if len(spath) > 1:
        path = spath[0]
        fragment = spath[1]

    if os.path.exists(path):
        head, base = os.path.split(path)
        mod = None

        if os.path.isfile(path) and path.endswith(".py"):
            modname = base[:-3]
            mod = load_pymod(head, modname)

        elif (os.path.isdir(path) and
                os.path.isfile(os.path.join(path, "__init__.py"))): 
            if base[-1] == os.sep:
                modname = base[:-1]

            else:
                modname = base

            mod = load_pymod(head, modname)
    else:
        try:
            modname = path
            mod = pyloco_import(modname)

        except ModuleNotFoundError as err:
            raise UsageError("path does not exist: %s" % path)

    if mod:
        if fragment:
            return fragment, getattr(mod, fragment)

        else:
            return modname, mod

def debug(*vargs):

    if all(vargs):
        import pdb; pdb.set_trace()
