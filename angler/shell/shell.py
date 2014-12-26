
import cmd
import os
import shlex
import sys
import traceback


class Shell(cmd.Cmd):
    def __init__(self, history, stdin=None, stdout=None, prompt='$',
                 exit_on_error=False):
        super(Shell, self).__init__(stdin=stdin, stdout=stdout)
        self.isatty = self.stdin.isatty()
        self.environment = dict()
        self.environment['prompt'] = prompt
        self.environment['prompt2'] = '>'
        self.multiline = ''
        self.exit_on_error = exit_on_error
        if history is not None:
            self.history = os.path.expanduser(history)
            try:
                import readline
                readline.read_history_file(self.history)
            except FileNotFoundError:
                pass
            except ImportError:
                pass
            else:
                import atexit
                atexit.register(readline.write_history_file, self.history)

    @property
    def prompt(self):
        if not self.isatty:
            return ''
        elif self.multiline:
            return self.environment['prompt2'] + ' '
        else:
            return self.environment['prompt'].format(**self.environment) + ' '

    @prompt.setter
    def prompt(self, new):
        self.environment['prompt'] = new

    def emptyline(self):
        pass

    def parseline(self, line):
        if self.multiline:
            line = '{}\n{}'.format(self.multiline, line)
        self.multiline = ''
        try:
            words = shlex.split(line, comments=True)
        except ValueError as error:
            if error.args == ('No closing quotation',):
                self.multiline = line
                return None, None, ''
            elif error.args == ('No escaped character',):
                self.multiline = line[:-1]
                return None, None, ''
            else:
                raise
        if not words:
            return None, None, ''
        cmd, arg = words[0], words[1:]
        return cmd, arg, line

    def default(self, line):
        if line == 'EOF':
            if self.isatty:
                print('exit')
            return self.do_exit('')
        else:
            return super(Shell, self).default(line)

    def do_exit(self, args):
        try:
            import readline
            last_index = readline.get_current_history_length()
            last_command = readline.get_history_item(last_index)
            if (last_command is not None and (last_command == 'exit'
                    or last_command.startswith('exit '))):
                readline.remove_history_item(last_index-1)
        except ImportError:
            pass
        return True

    def onecmd(self, line):
        try:
            return super(Shell, self).onecmd(line)
        except Exception as error:
            traceback.print_exc()
            return self.exit_on_error
