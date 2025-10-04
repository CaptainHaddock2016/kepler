import fsio
import ansi

def colorize(path, mode):
    """Return name string with ANSI color codes based on file type"""
    if mode != 32768:  # Directory
        return f"{ansi.blue}{path.name}{ansi.reset}"  # Blue for directories
    else:
        return path.name  # Default color

def main(argv, cwd):
    args = argv[1:]
    show_all = '-a' in args
    long_format = '-l' in args
    path = None
    for arg in args:
        if not arg.startswith('-'):
            path = arg
    if path:
        path = cwd.resolve(path)
    else:
        path = cwd
    try:
        entries = path.list()
    except Exception as e:
        return f"ls: cannot access '{path}': {e}"
    if not show_all:
        entries = [e for e in entries if not e.name.startswith('.')]
    entries.sort()
    output = []
    for entry in entries:
        full_path = path.join(entry)
        try:
            st = full_path.stat()
        except Exception:
            continue
        if long_format:
            output.append(format_long(entry, full_path, st[0]))
        else:
            output.append(colorize(entry, st[0]))
    if long_format:
        return '\n'.join(output)
    else:
        return '  '.join(output)
