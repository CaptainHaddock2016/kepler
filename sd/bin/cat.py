import fsio

def main(argv, cwd):
    args = argv[1:]
    path = fsio.Path(cwd).resolve(args[0])
    if path.exists():
        return path.read("r")
    else:
        return "cat: no such file or directory"