from mem import mem
import time

esp = mem.read("$esp")

def main(argv, cwd):
    esp.create_AP("Criminal Getaway Van", "password123")
    time.sleep(10000000)