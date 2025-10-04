def main(argv, cwd):
    args = argv[1:]
    objects = []
    for item in cwd.list():
        objects.append(str(item))
    return "  ".join(objects)
