import fsio

def main(argv, cwd):
    args = argv[1:]
    force = '-f' in args

    if args:
        path = cwd.resolve(args[0])
    else:
        return "rm: missing operand"
    
    if path.exists():
        if path.is_dir:
            if list(path.list()) and not force:
                return "rm: directory not empty"
            else:
                path.rm()
    