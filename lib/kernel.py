import fsio
import helpers
import displayio

KERNEL_TERMINAL_TILEGRID = None

# custom error for command not found
class CommandNotFoundError(Exception):
    pass

class ProgramExit(Exception):
    """Raised to indicate a program has requested to exit."""
    def __init__(self, code=0, message=""):
        self.code = code
        self.message = message
        super().__init__(f"Program exited with code {code}: {message}")

def exit_program(code=0, message=""):
    """Exit the current running program with an optional code."""
    raise ProgramExit(code, message)

# add exit to the namespace

ns = {"print": helpers.print, "input": helpers.input
      , "printf": helpers.printf, "exit": exit_program}

PATH = ["sd/bin", "bin"]

def findProgram(program, cwd):
    """Find command in cwd or PATH."""
    for ext in (".py", ".mpy"):
        p = cwd.join(f"{program}{ext}")
        if fsio.exists(str(p)):
            return p
        for dir in PATH:
            test = fsio.Path(f"{dir}/{program}{ext}", root=True)
            if fsio.exists(test):
                return test
    return None

def runProgram(program):
    # check if ends with .py or .pyw
    progPath = f"/applications/{program}/main.py"
    progPathWindowed = f"/applications/{program}/main.pyw"
    if fsio.exists(progPath, root=True):
        with open(progPath, "r") as f:
            data = f.read()
        # refactor when sd card works
        helpers.terminal = helpers.newTerminal()
        try: 
            exec(data, ns)
            ns.get("main", lambda *_: None)
        except ProgramExit as e:
            return f"Program exited with code {e.code}: {e.message}"
        except KeyboardInterrupt:
            pass
        finally:
            helpers.CURRENT_TERMINAL = helpers.KERNEL_TERMINAL
            helpers.CURRENT_TILEGRID = helpers.KERNEL_TILEGRID
            helpers.display.root_group.pop(0)
            helpers.display.root_group.append(helpers.KERNEL_TILEGRID)
    elif fsio.exists(progPathWindowed, root=True):
        with open(progPathWindowed, "r") as f:
            data = f.read()
        # set up windowed group

        progGroup = displayio.Group()
        term = helpers.display.root_group.pop(0)
        helpers.display.root_group.append(progGroup)
        helpers.display.refresh()

        ns.update({"group": progGroup, "refresh": helpers.display.refresh})
        try: 
            exec(data, ns)
            ns.get("main", lambda *_: None)
        except ProgramExit as e:
            return f"Program exited with code {e.code}: {e.message}"
        except KeyboardInterrupt:
            pass
        finally:
            helpers.display.root_group.pop(0)
            helpers.display.root_group.append(helpers.KERNEL_TILEGRID)
    else:
        raise CommandNotFoundError(f"Program '{program}' not found.")


def exe(program, args, cwd):
    progPath = findProgram(program, cwd)
    if progPath:
        try:
            exec(progPath.read(), ns)
            out = ns.get("main", lambda *_: None)(args, cwd)
            if out:
                return out
        except ProgramExit as e:
            return f"Program exited with code {e.code}: {e.message}"
        except KeyboardInterrupt:
            return "Program interrupted by user."
    else:
        raise CommandNotFoundError(f"Command '{program}' not found.")