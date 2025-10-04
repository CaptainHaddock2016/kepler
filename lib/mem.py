class Memory:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.data = {}   
        return cls._instance

    def write(self, key, value):
        self.data[key] = value

    def read(self, key, default=None):
        return self.data.get(key, default)

    def dump(self):
        return dict(self.data) 

mem = Memory()