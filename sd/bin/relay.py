import network

BROADCAST_IP = "255.255.255.255"
PORT = 5005

def main(argv, cwd):
    return "Not Implemented"
    sock = network.newSocket(network.AF_INET, network.SOCK_DGRAM)
    sock.connect(("", PORT))
    sock.settimeout(0.1)
    print("Starting chat. Type /exit to quit.")

    while True:
        msg = async_input("> ")
        if msg == "/exit":
            break
        elif msg:
            sock.sendto(msg.encode(), (BROADCAST_IP, PORT))
        
        try:
            data, addr = sock.recv(1024)
            print(f"\n[{addr[0]}] {data.decode()}\n> ", end="")
        except:
            continue