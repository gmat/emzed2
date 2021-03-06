import pdb
# encoding: utf-8

import datetime
import functools
import glob
import os
import socket
import sys
import tempfile
import thread
import time
import traceback
import weakref

import pyRserve
import pandas
import numpy as np

from ..data_types.table import guessFormatFor, Table

import patched_pyper as pyper


def data_frame_col_types(rip, value, name):
    rip.execute(""".__types <- sapply(%s, typeof); """ % name)
    type_strings = getattr(rip, ".__types")
    if isinstance(type_strings, basestring):
        type_strings = [type_strings]
    else:
        type_strings = type_strings.tolist()
    type_map = {"logical": bool, "integer": int, "double": float, "complex": complex,
                "character": str}
    py_types = [type_map.get(type_string, object) for type_string in type_strings]
    py_types = dict((str(n), t) for (n, t) in zip(value.columns, py_types))
    return py_types


def data_frame_to_table(rip, value, name, types=None, **kw):
    py_types = data_frame_col_types(rip, value, name)
    if types is not None:
        py_types.update(types)
    for name, t in py_types.items():
        values = None
        if t == int:
            # R factors -> string
            values = value[name].tolist()
            if all(isinstance(v, basestring) for v in values):
                py_types[name] = t = str
        if t == str:
            if values is None:
                values = value[name].tolist()
            if all(v in ("TRUE", "FALSE") for v in values):
                value[name] = [True if v == "TRUE" else False for v in values]
                py_types[name] = bool
    return Table.from_pandas(value, types=py_types, **kw)


class Bunch(dict):
    __getattr__ = dict.__getitem__


def find_r_exe_on_windows(required_version=""):

    assert sys.platform == "win32"
    import _winreg
    pathToR = None
    for finder in [
        lambda: _path_from(_winreg.HKEY_CURRENT_USER, required_version),
        lambda: _path_from(_winreg.HKEY_LOCAL_MACHINE, required_version),
        lambda: os.environ.get("R_HOME"),
        _parse_path_variable,
    ]:
        try:
            pathToR = finder()
            if pathToR is not None:
                break
        except (KeyError, WindowsError):
            pass
    if pathToR is None:
        raise Exception("install dir of R not found, neither in registry, nor is R_HOME set.")

    found = glob.glob("%s/bin/x64/R.exe" % pathToR)
    if not found:
        found = glob.glob("%s/bin/R.exe" % pathToR)
        if not found:
            raise Exception("could not find R.exe")
    return found[0]


def _parse_path_variable():
    for path in os.environ.get("PATH", "").split(os.pathsep):
        # windows
        if os.path.exists(os.path.join(path, "R.exe")):
            print "Found R at", path
            return path
        # non windows:
        test = os.path.join(path, "R")
        if os.path.exists(test) and not os.path.isdir(test):
            return test
    return None


def _path_from(regsection, required_version=""):
    assert sys.platform == "win32"
    import _winreg
    key = _winreg.OpenKey(regsection, "Software\\R-core\\R\\%s" % required_version)
    pathes = _winreg.QueryValueEx(key, "InstallPath")
    return _winreg.QueryValueEx(key, "InstallPath")[0]


class RInterpreter(object):

    """
    This class is the bridge to R. It creates a connection to a R process, it allows code
    execution and passes data to and from this process. For convinience R data.frame objects
    are converted to and from emzed Table objects.

    Example::

        >>> ip = emzed.r.RInterpreter()

        >>> ip.execute("a <- 3")
        >>> print ip.a
        3

        >>> ip.execute("tab <- data.frame(a=c(1, 2), b=c(2.1, 3))")
        >>> print ip.tab
        <emzed.core.data_types.table.Table object at 0x.......>

        >>> print ip.tab
        a        b
        int      float
        ------   ------
        1        2.100000
        2        3.000000

        >>> print ip.get_raw("x")    # returns pandas DataFrame
           a    b
        1  1  2.1
        2  2  3.0

    """

    def __init__(self, dump_stdout=True, r_exe=None, do_log=False, required_version="", **kw):
        """Starts a R process.

           In case of ``dump_stdout`` being ``True``, console output from R is imediatly
           dumped to the stdout of Python. This is helpful for long running scripts indicating
           their progress by printing status information, but may clutter the console,
           as lots of internal conversion operations are printed too.
        """
        if sys.platform != "win32" and required_version != "":
            import warnings
            warnings.warn("parameter 'required_version' ignored, works only on windows !")
        if r_exe is None:
            if sys.platform == "win32":
                r_exe = find_r_exe_on_windows(required_version)
            else:
                r_exe = "R"

        if do_log:
            self._create_new_log()
        else:
            self.__dict__["_fh"] = None

        try:
            if do_log:
                print >> self._fh, "\n# start subprocess %s at %s" % (r_exe, datetime.datetime.now())
                self._fh.flush()
            session = pyper.R(RCMD=r_exe, dump_stdout=dump_stdout, **kw)
        except:
            if do_log:
                print >> self._fh, "\n# failure"
                traceback.print_exc(file=self._fh)
                self._fh.flush()
                self._fh.close()
                del self._fh
            raise Exception("could not start R, is R installed ?")
        self.__dict__["session"] = session

    def _create_new_log(self):
        if "_fh" in self.__dict__:
            self.__dict__["_fh"].flush()
            self.__dict__["_fh"].close()
        if sys.platform == "darwin":
            tempfile.tempdir = "/tmp"   # else the path is very complicated.
        path = os.path.join(tempfile.mkdtemp(), "log.txt")
        print
        print ">>>>>>>>>>> START TO LOG TO", path
        print
        self.__dict__["_fh"] = open(path, "w")

    def __dir__(self):
        """ avoid completion in IPython shell, as attributes are automatically looked up in
        overriden __getattr__ method
        """
        return ["execute", "get_df_as_table", "get_raw"]

    def execute(self, *cmds, **kw):
        """executes commands. Each command may be a multiline command. 
           **kw is used for easier string interpolation, eg

              rip.execute("x <- %(name)r", name="emzed")

           instead of

              rip.execute("x <- %(name)r" % dict(name="emzed"))
           """
        has_fh = self.__dict__.get("_fh") is not None
        if has_fh:
            print >> self._fh, "#", datetime.datetime.now()
            self._fh.flush()
        for cmd in cmds:
            if has_fh:
                print >> self._fh, cmd
                self._fh.flush()
            if kw:
                cmd = cmd % kw
            self.session(cmd)

        if has_fh:
            print >> self._fh, "#", 60 * "="
            self._fh.flush()
        return self

    def execute_file(self, path):
        """execute r scripts described by path

           if path is only a file name the directory of the calling functions __file__ is used
           for looking up the r script.
           use "./abc.r" notation if you want to get script from the current working directory.
        """

        if os.path.dirname(path) == "":   # only file name
            import inspect
            calling_file = inspect.stack()[1][0].f_globals.get("__file__")
            if calling_file is not None:
                path = os.path.join(os.path.dirname(os.path.abspath(calling_file)), path)
        has_fh = self.__dict__.get("_fh") is not None
        if has_fh:
            print >> self._fh, "#", datetime.datetime.now()
            print >> self._fh, "# execute", path
            self._fh.flush()
        with open(path, "r") as fp:
            cmd = fp.read()
            if has_fh:
                print >> self._fh, cmd
                self._fh.flush()
            self.session(cmd)
        if has_fh:
            print >> self._fh, "#", 60 * "="
            self._fh.flush()
        return self

    def get_df_as_table(self, name, title=None, meta=None, types=None, formats=None):
        """
        Transfers R data.frame object with name ``name`` to emzed Table object.
        For the remaining paramters see :py:meth:`~emzed.core.data_types.table.Table.from_pandas`
        """
        native = getattr(self.session, name)
        assert isinstance(native, pandas.DataFrame), "expected data frame, got %s" % type(native)

        return data_frame_to_table(self, native, name, types=types, title=title, meta=meta, formats=formats)
        py_types = data_frame_col_types(self, native, name)
        return Table.from_pandas(native, title, meta, py_types, formats)

    def get_raw(self, name):
        """
        returns data.frame as pandas DataFrame, etc.
        no converstion to emzed Table data structure
        """
        return self.__getattr__(name, False)

    def __getattr__(self, name, convert_to_table=True):
        # IPython 0.10 does strange things for completion, so we circument them:
        if name == "trait_names" or name == "_getAttributeNames":
            return []
        # IPython 0.10 has an error for ip.execute("x <- data.frame()") as it tries to lookup
        # attribute 'execute("x <- data")', I think this is driven by the dot in "data.frame"
        if name.startswith("execute("):
            return []
        if hasattr(self, "session"):
            value = getattr(self.session, name)
            if convert_to_table and isinstance(value, pandas.DataFrame):
                return data_frame_to_table(self, value, name)
            return value

    def __setattr__(self, name, value):
        has_fh = self.__dict__.get("_fh") is not None
        if has_fh:
            if isinstance(value, (list, tuple)):
                s_value = "c%r" % (tuple(value),)
                s_value = s_value.replace(",)", ")")
            else:
                s_value = repr(value)
            print >> self._fh, "%s <- %s" % (name, s_value)
            self._fh.flush()
        if isinstance(value, Table):
            value = value.to_pandas()
        setattr(self.session, name, value)


def shutdown_on_error(fun):
    @functools.wraps(fun)
    def wrapped(self, *a, **kw):
        try:
            return fun(self, *a, **kw)
        except:
            self.shutdown()
            raise
    return wrapped


class RInterpreterFast(object):

    def __init__(self, dump_stdout=True, r_exe=None, do_log=False, port=None, **kw):

        if port is None:
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.close()
        rip = RInterpreter(r_exe=r_exe, **kw)
        rip.execute("""if("Rserve" %in% rownames(installed.packages()) == FALSE)
                        {
                          install.packages("Rserve", repos="http://cran.rstudio.com");
                        }
                    """)
        cmd = """library(Rserve);
                 Rserve::run.Rserve(port=%d);
              """ % port
        thread.start_new_thread(rip.execute, (cmd,))
        self.__dict__["dump_stdout"] = dump_stdout

        for _ in range(10):
            try:
                self.__dict__["conn"] = pyRserve.connect(host="127.0.0.1", port=port)
            except pyRserve.rexceptions.RConnectionRefused:
                time.sleep(0.1)
            else:
                break
        else:
            raise Exception("connection failed after 10 trials over one second in total")

        def on_die(killed_ref, conn=self.conn):
            # we pass conn here because access to self ist not allowed in this handler.
            # further we import socket inside because this function maybe called when the Python
            # interpreter is shut down and a globally imported module socket might not be available
            # any more
            import socket
            try:
                conn.shutdown()
            except socket.error:
                pass

        # instead of implementing __del__ to force shutdown if the object dies, we use the
        # weakref trick to trigger shutdown at the end of self's life:
        self.__dict__["_del_ref"] = weakref.ref(self, on_die)

    @shutdown_on_error
    def execute(self, r_code, **kw):
        # we put our (potentially multiline) r code into a function so that we can use
        # capture.output to pass output to python back.
        # the eval.parent(substitute(..))) injects all variables in this function
        # to the global R environment. so code as "x <- 3" is executed inside the .__run
        # function but then x is globally set:

        # kw is easier way to provide strint interpolation
        if kw:
            r_code = r_code % kw
        self.conn.eval(""".__run <- function() eval.parent(substitute({%s})); """ % r_code)
        if self.dump_stdout:
            self.conn.eval("""capture.output(.__run(), file=pipe("cat"))""")
        else:
            self.conn.eval("""__run();""")
        return self

    @shutdown_on_error
    def execute_file(self, path):
        """execute r scripts described by path

           if path is only a file name the directory of the calling functions __file__ is used
           for looking up the r script.
           use "./abc.r" notation if you want to get script from the current working directory.
        """

        if os.path.dirname(path) == "":   # only file name
            import inspect
            calling_file = inspect.stack()[1][0].f_globals.get("__file__")
            if calling_file is not None:
                path = os.path.join(os.path.dirname(os.path.abspath(calling_file)), path)
        self.conn.eval("""capture.output(source("%s"), file=pipe("cat"))""" % path)
        return self

    def shutdown(self):
        self.conn.shutdown()

    @shutdown_on_error
    def _fetch(self, name):
        self.execute("""
            .__value <- %s;
            if (typeof(.__value) == "list") {
                .__ii = sapply(.__value, is.factor);
                .__value[.__ii] <- lapply(.__value[.__ii], as.character);
            }
        """ % name)
        value = getattr(self.conn.r, ".__value")
        return value

    def _tagged_list_to_emzed(self, value, name, title=None, meta=None, types=None, formats=None):
        self.execute(""".__is_df <- class(%s) == "data.frame"; """ % name)
        is_df = getattr(self.conn.r, ".__is_df")
        if not is_df:
            assert title is None
            assert meta is None
            assert types is None
            assert formats is None
            items = []
            for sub_name, value in value.astuples():
                if isinstance(value, pyRserve.TaggedList):
                    value = self._tagged_list_to_emzed(value, "%s$%s" % (name, sub_name))
                items.append((sub_name, value))
            return Bunch(items)

        return self._tagged_list_to_table(value, name, title, meta, types, formats)

    def _tagged_list_to_table(self, value, name, title, meta, types, formats):
        self.execute(""".__types <- sapply(%s, typeof); """ % name)
        type_strings = getattr(self.conn.r, ".__types").tolist()

        if types is None:
            types = {}
        if formats is None:
            formats = {}

        col_names = map(str, value.keys)
        col_values = value.values

        type_map = {"logical": bool, "integer": int, "double": float, "complex": complex,
                    "character": str}
        py_types = [type_map.get(type_string, object) for type_string in type_strings]
        col_types = [types.get(n, t) for n, t in zip(col_names, py_types)]

        guessed_formats = [guessFormatFor(n, t) for (n, t) in zip(col_names, col_types)]
        col_formats = []
        for n, t, f in zip(col_names, col_types, guessed_formats):
            f0 = formats.get(n, 0)   # 0 instead of None, because None might be set intentionally
            if f0 == 0:
                f0 == formats.get(t, 0)
                if f0 == 0:
                    f0 = f
            col_formats.append(f0)

        if not all(isinstance(v, np.ndarray) for v in col_values):
            # one column data frames come as tagged list with float, etc values, not with arrays
            rows = [list(col_values)]
        else:
            # transpose column matrix and convert tuples to lists
            rows = map(list, zip(*col_values))

        return Table(col_names, col_types, col_formats, rows, title, meta)

    def _tagged_list_to_pandas(self, tagged_list):
        as_dict = dict(tagged_list.astuples())
        return pandas.DataFrame(as_dict)

    def _table_to_tagged_list(self, t):
        names = t.getColNames()
        cols = map(np.array, zip(*t.rows))
        return pyRserve.TaggedList(zip(names, cols))

    def _pandas_to_tagged_list(self, df):
        names = df.columns.tolist()
        cols = map(np.array, zip(*df.as_matrix()))
        return pyRserve.TaggedList(zip(names, cols))

    @shutdown_on_error
    def __getattr__(self, name):
        # IPython 0.10 does strange things for completion, so we circument them:
        if name == "trait_names" or name == "_getAttributeNames":
            return []
        # IPython 0.10 has an error for ip.execute("x <- data.frame()") as it tries to lookup
        # attribute 'execute("x <- data")', I think this is driven by the dot in "data.frame"
        if name.startswith("execute("):
            return []

        value = self._fetch(name)
        if isinstance(value, pyRserve.TaggedList):
            return self._tagged_list_to_emzed(value, name)
        return value

    @shutdown_on_error
    def __setattr__(self, name, value):
        if isinstance(value, Table):
            tl = self._table_to_tagged_list(value)
            setattr(self.conn.r, name, tl)
            if len(value.getColNames()) == 1:
                # if table has one column the R value is a list, not a data frame, so:
                self.execute("""%s <- data.frame(%s)""" % (name, name))
            return
        elif isinstance(value, pandas.DataFrame):
            value = self._pandas_to_tagged_list(value)
        elif isinstance(value, tuple):
            self.execute("""%s <- c%r""" % (name, value))
            return
        setattr(self.conn.r, name, value)

    @shutdown_on_error
    def get_df_as_table(self, name, title=None, meta=None, types=None, formats=None):
        """
        Transfers R data.frame object with name ``name`` to emzed Table object.
        For the remaining paramters see :py:meth:`~emzed.core.data_types.table.Table.from_pandas`
        """
        value = self._fetch(name)
        if isinstance(value, pyRserve.TaggedList):
            return self._tagged_list_to_table(value, name, title, meta, types, formats)

    def get_raw(self, name):
        value = self._fetch(name)
        if isinstance(value, pyRserve.TaggedList):
            return self._tagged_list_to_pandas(value)
        return value

    def __dir__(self):
        """ avoid completion in IPython shell, as attributes are automatically looked up in
        overriden __getattr__ method
        """
        return ["execute", "shutdown", "get_df_as_table", "get_raw"]
