import os
import time

class Path:
    def __init__(self, path="", root=False):
        # Detect when user passed "/" as actual root
        if isinstance(path, Path):
            self.path = path.path
            self.root = path.root
        else:
            self.root = root
            if isinstance(path, str):
                if path == "/":
                    self.path = ""
                else:
                    self.path = self._normalize(path)
            else:
                raise ValueError("Invalid argument. Must be either string or Path")

        self.name = self._name()

    def _normalize(self, path):
        parts = []
        for part in path.split("/"):
            if part == "" or part == ".":
                continue
            elif part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        return "/".join(parts)

    def join(self, subpath):
        """Join paths and preserve root flag"""
        if isinstance(subpath, Path):
            subpath = str(subpath)

        # Absolute override: "/foo"
        if subpath.startswith("/"):
            return Path(self._normalize(subpath), root=self.root)

        # Relative combine
        return Path(self._normalize(f"{self.path}/{subpath}"), root=self.root)

    @property
    def parent(self):
        parts = self.path.split("/")
        return Path("/".join(parts[:-1]) if len(parts) > 1 else "", root=self.root)

    def _kernel_path(self):
        """Return the actual filesystem path for OS operations."""
        if self.root:
            # Real OS root
            return "/" + self.path if self.path else "/"
        else:
            # Virtual FS under sd/
            return f"sd/{self.path}"

    def stat(self):
        return os.stat(self._kernel_path())

    @property
    def is_dir(self):
        return isDir(self)

    def exists(self):
        return exists(self)

    def pstr(self):
        s = "/" + self.path if self.path else "/"
        return s.replace("/root/home", "~")

    def read(self, mode="r"):
        with open(self._kernel_path(), mode) as f:
            return f.read()

    def write(self, buffer, mode="w"):
        with open(self._kernel_path(), mode) as f:
            return f.write(buffer)

    def list(self):
        if not self.is_dir:
            return
        base_path = self._kernel_path()
        for entry in os.listdir(base_path):
            yield self.join(entry)

    def resolve(self, other):
        if other.startswith("/"):
            return Path(self._normalize(other), root=self.root)
        return self.join(other)

    def rm(self):
        p = self._kernel_path()
        if self.is_dir:
            os.rmdir(p)
        else:
            os.remove(p)

    def _name(self):
        return self.path.split("/")[-1]

    def __lt__(self, other):
        return self.name < other.name

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"Path('{self.path}', root={self.root})"


def _to_str(path):
    return str(path) if isinstance(path, Path) else str(path)

def exists(path, root=False):
    if isinstance(path, Path):
        p = path._kernel_path()
    else:
        if root:
            p = f"/{path}"
        else:
            p = f"sd/{path}"
    try:
        os.stat(p)
    except:
        return False
    return True

def isDir(path):
    if not exists(path):
        return None
    p = path._kernel_path() if isinstance(path, Path) else f"sd/{path}"
    st = os.stat(p)
    # stat.S_IFREG == 32768 → file
    return st[0] != 32768

def mkdir(path):
    p = path._kernel_path() if isinstance(path, Path) else f"sd/{path}"
    os.mkdir(p)

if not exists("var"):
    mkdir("var")
with open("sd/var/log.txt", "a") as f:
    f.write(f"{time.time()} FSIO Initalized\n")
