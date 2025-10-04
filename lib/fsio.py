import os
import time

class Path:
    def __init__(self, path=""):
        # Normalize to avoid accidental double slashes
        if isinstance(path, Path):
            self.path = path.path
        elif isinstance(path, str):
            self.path = self._normalize(path)
        else:
            raise ValueError("Invalid argument. Must be either string or Path")
        self.name = self._name()

    def _normalize(self, path):
        """Normalize path to remove redundant slashes and resolve '.' """
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
        """Return a new Path object joined with subpath"""
        if isinstance(subpath, Path):
            subpath = str(subpath)
        if subpath.startswith("/"):
            # Absolute override
            return Path(self._normalize(subpath))
        return Path(self._normalize(f"{self.path}/{subpath}"))

    @property
    def parent(self):
        """Return the parent directory of this path"""
        parts = self.path.split("/")
        return Path("/".join(parts[:-1])) if len(parts) > 1 else Path("")
    
    def stat(self):
        """Return os.stat result for this path"""
        return os.stat(self._kernel_path())

    @property
    def is_dir(self):
        """Check if path is directory using your OS functions"""
        return isDir(self)

    def exists(self):
        """Check if path exists using your OS functions"""
        return exists(self)
    
    def pstr(self):
        """
        Return a pretty string for terminal display:
        Always starts with '/', ends with '/' if it's a directory.
        """
        s = "/" + self.path if self.path else "/"
        return s.replace("/root/home", "~")
    
    def read(self, mode="r"):
        with open(self._kernel_path(), mode) as f:
            buffer = f.read()
        return buffer
    
    def write(self, buffer, mode="w"):
        with open(self._kernel_path(), mode) as f:
            n = f.write(buffer)
        return n
    
    def list(self):
        """Generator to yield all files and directories under this path"""
        base_path = str(self)
        if not self.is_dir:
            return
        for entry in os.listdir(f"sd/{base_path}"):
            yield Path(entry)
    
    def resolve(self, other):
        """
        Takes another Path (or string). 
        If it's a relative path, return its absolute version relative to self. 
        If it's absolute, return it normalized.
        """
        other = str(other)

        # Absolute path: starts with '/'
        if other.startswith("/"):
            return Path(self._normalize(other))

        # Relative path: join to current path
        return self.join(other)
    
    def rm(self):
        """Remove this file or directory"""
        if self.is_dir:
            os.rmdir(self._kernel_path())
        else:
            os.remove(self._kernel_path())
    
    def _kernel_path(self):
        """Return the path as used by the underlying OS (with 'sd/' prefix)"""
        return f"sd/{self.path}"
    
    def _name(self):
        """Return final element (file or dir name)"""
        return self.path.split("/")[-1]
    
    def __lt__(self, other):
        return self.name < other.name
    
    def __str__(self):
        return self.path

    def __repr__(self):
        return f"Path('{self.path}')"

def _to_str(path):
    """Convert Path or string to normalized string"""
    if isinstance(path, Path):
        return str(path)
    return str(path)

def exists(path):
    p = _to_str(path)
    try:
        os.stat(f"sd/{p}")
    except:
        return False
    return True

def isDir(path):
    p = _to_str(path)
    if not exists(p):
        return None
    fType = os.stat(f"sd/{p}")
    if fType[0] == 32768:
        return False
    return True        

def mkdir(path):
    p = _to_str(path)
    os.mkdir(f"sd/{p}")

if not exists("var"):
    mkdir("var")
with open("sd/var/log.txt", "a") as f:
    f.write(f"{time.time()} FSIO Initalized\n")
