# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>
import logging
import os
from cmd import Cmd

import bpy

bl_info = {
    "name": "Logging Console",
    "author": "Isaac Weaver",
    "version": (0, 1),
    "blender": (2, 78, 0),
    "location": "Console > Console Menu > Languages > Logging",
    "description": "Custom console for viewing logging output.",
    "warning": "Alpha.",
    "tracker_url": "https://github.com/wisaac407/blender-logger-console/issues/new",
    "category": "Development",
}

language_id = "logging"
PROMPT = '$ '


def add_scrollback(text, text_type, ctx=None):
    if ctx is None:
        ctx = bpy.context.copy()
    for l in text.split("\n"):
        bpy.ops.console.scrollback_append(ctx, text=l.replace("\t", "    "),
                                          type=text_type)


class ScrollBackIO:
    """Simple StringIO type object that will write to the console scrollback"""

    def __init__(self, context, typ='OUTPUT'):
        self._context = context.copy()
        self._type = typ
        self._buffer = ''

    def write(self, s):
        self._buffer += s

        if '\n' in self._buffer:
            scrollback, self._buffer = self._buffer.rsplit('\n', 1)
            add_scrollback(scrollback, self._type, ctx=self._context)

    def writeline(self, s=''):
        self.write(s)
        self.write('\n')


LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


def _logger_completer_factory(watched_only=False):
    def complete_loggers(self, text, *ignore):
        options = []
        loggers = self._handlers if watched_only else self.get_loggers_flat()
        for logger in loggers:
            if logger.startswith(text):
                logger = text + logger[len(text):].split('.', 1)[0]
                if logger not in options:
                    options.append(logger)
        return options

    return complete_loggers


class LoggingCmd(Cmd):
    prompt = PROMPT
    indent = '    '

    def __init__(self, **kwargs):
        super(LoggingCmd, self).__init__(**kwargs)
        self._handlers = {}

    def get_loggers_flat(self):
        return list(logging.Logger.manager.loggerDict.keys())

    def get_loggers(self):
        def unflatten(loggers_flat):
            loggers = {}
            for logger in loggers_flat:
                if '.' in logger:
                    top, subs = logger.split('.', 1)
                    loggers.setdefault(top, []).append(subs)
                else:
                    loggers.setdefault(logger, [])

            for name, loggers_flat in loggers.items():
                loggers[name] = unflatten(loggers_flat)
            return loggers

        return unflatten(self.get_loggers_flat())

    def get_logger_children(self, logger):
        loggers = self.get_loggers()
        parts = logger.split('.')
        for part in parts:
            loggers = loggers[part]
        return loggers

    @staticmethod
    def get_word_span(line, current_pos):
        word = ''
        begidx = 0
        endidx = 0

        # Add a space at the end of the line to force to set the endidx if needed
        for i, c in enumerate(line + ' '):
            if c == ' ':
                endidx = i

                if i >= current_pos:
                    break
                word = ''
                begidx = i + 1
            else:
                word += c

        return begidx, endidx

    def complete(self, line, current_pos):
        """Return the next possible completion for 'text'.

        If a command has not been entered, then complete against command list.
        Otherwise try to call complete_<command> to get list of completions.
        """

        begidx, endidx = self.get_word_span(line, current_pos)
        endidx = current_pos

        text = line[begidx:endidx]
        print(text)

        if begidx > 0:
            cmd, args, foo = self.parseline(line)
            if cmd == '':
                compfunc = self.completedefault
            else:
                try:
                    compfunc = getattr(self, 'complete_' + cmd)
                except AttributeError:
                    compfunc = self.completedefault
        else:
            compfunc = self.completenames
        return compfunc(text, line, begidx, endidx), begidx, endidx

    _complete_loggers = _logger_completer_factory()
    _complete_watched_loggers = _logger_completer_factory(True)

    def do_clear(self, arg):
        """Clear the console"""
        # bpy.ops.console.clear()
        self.stdout.write('\n' * int(bpy.context.region.height / bpy.context.space_data.font_size))

    def do_list_loggers(self, arg):
        """List loggers"""
        print_prefixes = True

        indent = self.indent

        if arg:
            try:
                loggers = self.get_logger_children(arg)
            except KeyError:
                self.stdout.writeline('No such logger: ' + arg)
                return
        else:
            loggers = self.get_loggers()

        if len(loggers) == 0:
            self.stdout.writeline('*** No child loggers found')
        else:
            if print_prefixes:
                prefix = (arg + '.') if arg else ''

                for logger in loggers:
                    self.stdout.writeline(indent + prefix + logger)
            else:
                self.stdout.writeline(indent + ('\n' + indent).join(loggers.keys()))

    do_ll = do_list_loggers

    complete_list_loggers = _complete_loggers
    complete_ll = _complete_loggers

    def do_list_all(self, arg):
        """List all loggers"""
        indent = self.indent
        self.stdout.writeline(indent + ('\n' + indent).join(sorted(self.get_loggers_flat())))

    do_la = do_list_all

    def do_tree(self, arg):
        """List all the loggers in a tree format"""
        indent = self.indent
        use_pipes = True
        inner_indent = '%s   ' % chr(9474)

        def tree_level(loggers, prefix):
            total = len(loggers)
            for i, logger in enumerate(loggers):
                is_last = total - i == 1

                if use_pipes:
                    _prefix = prefix + (
                        '%s%s%s ' % (chr(9492 if is_last else 9500), chr(9472), chr(9472))
                    )
                else:
                    _prefix = prefix + indent

                self.stdout.writeline(_prefix + logger)
                tree_level(loggers[logger], prefix + (indent if is_last else inner_indent))

        if arg:
            logger = arg
            try:
                loggers = self.get_logger_children(arg)
            except KeyError:
                self.stdout.writeline('No such logger: ' + prefix.join('.'))
                return
        else:
            logger = 'root'
            loggers = self.get_loggers()

        self.stdout.writeline(indent + logger)
        tree_level(loggers, indent)

    complete_tree = _complete_loggers

    def do_watch(self, arg):
        """Watch logger and print it's output"""
        if arg in self._handlers:
            self.stdout.writeline('*** Logger already being watched')
            return
        try:
            logger = logging.Logger.manager.loggerDict[arg]
        except KeyError:
            self.stdout.writeline('*** No logger found with name: ' + arg)
            return

        try:
            handler = logging.StreamHandler(self.stdout)
            handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
            logger.addHandler(handler)
            self._handlers[arg] = handler
        except AttributeError:
            self.stdout.writeline('*** Not a top level logger')

    complete_watch = _complete_loggers

    def do_unwatch(self, arg):
        """Stop watch a handler"""

        try:
            handler = self._handlers.pop(arg)
            logger = logging.Logger.manager.loggerDict[arg]
            logger.removeHandler(handler)
        except KeyError:
            self.stdout.writeline('*** Logger not being watched')

    complete_unwatch = _complete_watched_loggers

    def do_watching(self, arg):
        """List all the loggers being watched"""
        indent = self.indent
        if len(self._handlers):
            self.stdout.writeline(indent + ('\n' + indent).join(self._handlers.keys()))
        else:
            self.stdout.writeline('*** No loggers being watched')

    def do_set_level(self, arg):
        """Set the report level for a watched logger (warning changes the report level on the logger itself)"""
        try:
            logger, level = arg.split(' ')
        except ValueError:
            self.stdout.writeline('*** Must be in the format: set_level <logger> <level>')
            return

        handler = self._handlers.get(logger)
        if handler is None:
            self.stdout.writeline('*** Can only change the level on watched loggers')
            return

        try:
            logging.getLogger(logger).setLevel(LEVELS[level])
        except KeyError:
            self.stdout.writeline('*** Unknown level: ' + level)
    
    def complete_set_level(self, text, line, begidx, endidx):
        prefix = line[:begidx].strip().split()

        if len(prefix) == 1:
            # Complete first argument
            return self._complete_watched_loggers(text)
        else:
            # Complete second argument
            options = []
            for level in LEVELS:
                if level.startswith(text):
                    options.append(level)
            return options

def get_console(console_id):
    """
    helper function for console operators
    currently each text data block gets its own
    console - code.InteractiveConsole()
    ...which is stored in this function.

    console_id can be any hashable type
    """

    consoles = getattr(get_console, "consoles", None)
    hash_next = hash(bpy.context.window_manager)

    if consoles is None:
        consoles = get_console.consoles = {}
        get_console.consoles_namespace_hash = hash_next
    else:
        # check if clearing the namespace is needed to avoid a memory leak.
        # the window manager is normally loaded with new blend files
        # so this is a reasonable way to deal with namespace clearing.
        # bpy.data hashing is reset by undo so cant be used.
        hash_prev = getattr(get_console, "consoles_namespace_hash", 0)

        if hash_prev != hash_next:
            get_console.consoles_namespace_hash = hash_next
            consoles.clear()

    console = consoles.get(console_id)

    if console is None:
        console = LoggingCmd(stdout=ScrollBackIO(bpy.context))
        consoles[console_id] = console

    return console


def execute(context, is_interactive):
    sc = context.space_data

    try:
        line = sc.history[-1].body
    except:
        return {'CANCELLED'}

    console = get_console(hash(context.region))

    # Add the prompt to the scrollback
    bpy.ops.console.scrollback_append(text=sc.prompt + line, type='INPUT')

    # Execute the command
    console.onecmd(line)

    # insert a new blank line
    bpy.ops.console.history_append(text="", current_character=0,
                                   remove_duplicates=True)

    sc.prompt = console.prompt
    return {'FINISHED'}


# See: https://stackoverflow.com/a/6718435/4103890
def longest_common_prefix(m):
    """Given a list of strings, returns the longest common leading component"""
    if not m: return ''
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1


def autocomplete(context):
    sc = context.space_data
    
    current_line = sc.history[-1]

    console = get_console(hash(context.region))

    cursor_pos = current_line.current_character
    line = current_line.body

    options, begidx, endidx = console.complete(line, cursor_pos)
    prefix = longest_common_prefix(options)

    prefix = prefix[endidx - begidx:]

    line = line[:cursor_pos] + prefix + line[cursor_pos:]
    cursor_pos += len(prefix)

    current_line.body = line
    current_line.current_character = cursor_pos

    if options:
        add_scrollback(sc.prompt + current_line.body, 'INPUT')
        add_scrollback('\n'.join(options), 'INFO')
    
    return {'CANCELLED'}


def banner(context):
    sc = context.space_data

    add_scrollback("""Welcome!""", 'OUTPUT')

    sc.prompt = PROMPT

    return {'FINISHED'}


def register():
    pass


def unregister():
    import sys
    sys.modules.pop('console_logging')
