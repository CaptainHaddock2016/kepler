import os
import shutil

import fsio

USAGE = "Usage: editor <filename>"


def _to_os_path(path: fsio.Path) -> str:
    relative = str(path)
    if relative:
        return os.path.join("sd", relative)
    return "sd"


def main(argv, cwd):
    args = argv[1:]
    if not args:
        return USAGE

    target = fsio.Path(cwd).resolve(args[0])

    if target.exists() and target.is_dir:
        return f"editor: '{target.pstr()}' is a directory"

    parent = target.parent
    if str(parent) and not parent.exists():
        return f"editor: directory '{parent.pstr()}' does not exist"

    vim_path = shutil.which("vim")
    if not vim_path:
        return "editor: vim executable not found"

    os_path = _to_os_path(target)
    os.execv(vim_path, ["vim", os_path])
