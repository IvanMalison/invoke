import io
import os
import sys

from spec import Spec, trap, eq_, skip, ok_

from invoke.vendor import six

from invoke import run
from invoke._version import __version__
from invoke.platform import WINDOWS

from _util import only_utf8


def _output_eq(cmd, expected):
    return eq_(run(cmd, hide=True).stdout, expected)


class Main(Spec):
    def setup(self):
        # Enter integration/ so Invoke loads its local tasks.py
        os.chdir(os.path.dirname(__file__))

    @trap
    def basic_invocation(self):
        _output_eq("invoke print_foo", "foo\n")

    @trap
    def version_output(self):
        _output_eq("invoke --version", "Invoke {0}\n".format(__version__))

    @trap
    def help_output(self):
        ok_("Usage: inv[oke] " in run("invoke --help").stdout)

    @trap
    def shorthand_binary_name(self):
        _output_eq("inv print_foo", "foo\n")

    @trap
    def explicit_task_module(self):
        _output_eq("inv --collection _explicit foo", "Yup\n")

    @trap
    def invocation_with_args(self):
        _output_eq(
            "inv print_name --name whatevs",
            "whatevs\n"
        )

    @trap
    def bad_collection_exits_nonzero(self):
        result = run("inv -c nope -l", warn=True)
        eq_(result.exited, 1)
        assert not result.stdout
        assert result.stderr

    def loads_real_user_config(self):
        path = os.path.expanduser("~/.invoke.yaml")
        try:
            with open(path, 'w') as fd:
                fd.write("foo: bar")
            _output_eq("inv print_config", "bar\n")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def complex_nesting_under_ptys_doesnt_break(self):
        if WINDOWS: # Not sure how to make this work on Windows
            return
        # GH issue 191
        substr = "      hello\t\t\nworld with spaces"
        cmd = """ eval 'echo "{0}" ' """.format(substr)
        expected = '      hello\t\t\r\nworld with spaces\r\n'
        eq_(run(cmd, pty=True, hide='both').stdout, expected)

    def KeyboardInterrupt_on_stdin_doesnt_flake(self):
        # E.g. inv test => Ctrl-C halfway => shouldn't get buffer API errors
        skip()

    class funky_characters_in_stdout:
        def setup(self):
            class BadlyBehavedStdout(io.TextIOBase):
                def write(self, data):
                    if six.PY2 and not isinstance(data, six.binary_type):
                        data.encode('ascii')
            self.bad_stdout = BadlyBehavedStdout()

        @only_utf8
        def basic_nonstandard_characters(self):
            os.chdir('_support')
            # Crummy "doesn't explode with decode errors" test
            cmd = ("type" if WINDOWS else "cat") + " tree.out"
            run(cmd, hide='stderr', out_stream=self.bad_stdout)

        @only_utf8
        def nonprinting_bytes(self):
            # Seriously non-printing characters (i.e. non UTF8) also don't
            # asplode (they would print as escapes normally, but still)
            run("echo '\xff'", hide='stderr', out_stream=self.bad_stdout)

        @only_utf8
        def nonprinting_bytes_pty(self):
            if WINDOWS:
                return
            # PTY use adds another utf-8 decode spot which can also fail.
            run("echo '\xff'", pty=True, hide='stderr',
                out_stream=self.bad_stdout)

    def pty_puts_both_streams_in_stdout(self):
        if WINDOWS:
            return
        os.chdir('_support')
        err_echo = "{0} err.py".format(sys.executable)
        command = "echo foo && {0} bar".format(err_echo)
        r = run(command, hide='both', pty=True)
        eq_(r.stdout, 'foo\r\nbar\r\n')
        eq_(r.stderr, '')

    def simple_command_with_pty(self):
        """
        Run command under PTY
        """
        # Most Unix systems should have stty, which asplodes when not run under
        # a pty, and prints useful info otherwise
        result = run('stty -a', hide=True, pty=True)
        # PTYs use \r\n, not \n, line separation
        ok_("\r\n" in result.stdout)
        eq_(result.pty, True)

    def pty_size_is_realistic(self):
        # When we don't explicitly set pty size, 'stty size' sees it as 0x0.
        # When we do set it, it should be some non 0x0, non 80x24 (the default)
        # value. (yes, this means it fails if you really do have an 80x24
        # terminal. but who does that?)
        size = run('stty size', hide=True, pty=True).stdout.strip()
        assert size != ""
        assert size != "0 0"
        # Apparently true-headless execution like Travis does that!
        if os.environ.get('TRAVIS', False):
            assert size == "24 80"
        else:
            assert size != "24 80"
