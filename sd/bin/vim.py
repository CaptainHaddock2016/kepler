import os
import shutil

import fsio


def _path_string(path):
    if hasattr(path, "pstr"):
        return path.pstr()
    return str(path)


def main(argv, cwd):
    if shutil.which("vim") is None:
        return "vim: command not found"

    base = fsio.Path(cwd)
    workdir = _path_string(base)

    try:
        previous = os.getcwd()
    except OSError:
        previous = None

    try:
        os.chdir(workdir)
    except Exception as exc:
        return f"vim: cannot change directory to '{workdir}': {exc}"

    command = ["vim", *argv[1:]]

    try:
        os.execvp(command[0], command)
    except OSError as exc:
        if previous is not None:
            try:
                os.chdir(previous)
            except Exception:
                pass
        return f"vim: failed to launch: {exc}"
