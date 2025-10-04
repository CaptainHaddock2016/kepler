from mem import mem

SOCK_POOL = mem.read("$socketpool")
AF_INET = SOCK_POOL.AF_INET
SOCK_DGRAM = SOCK_POOL.SOCK_DGRAM
SOCK_STREAM = SOCK_POOL.SOCK_STREAM

def newSocket(family: int = AF_INET, type: int = SOCK_STREAM, proto: int = 0):
    return mem.read("$socketpool").socket(family, type, proto)