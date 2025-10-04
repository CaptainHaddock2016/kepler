def main(argv, cwd):
    args = argv[1:]
    total = sum(int(x) for x in args)
    print(total)