import socket
import json

class Client:
    def __init__(self, hostpair, name):
        self._socket = socket.socket()
        self._socket.connect(hostpair)
        self._socket.send(name.encode())

    def recv(self):
        while True:
            data = self._socket.recv(1024).decode()
            if not data:
                raise OSError
            parts = data.split("\n")
            for part in parts:
                part = part.strip()
                if part:
                    yield tuple(json.loads(part).items())[0]

    def respond(self, data):
        return self._socket.send(data.encode())

    def run(self):
        try:
            for action, data in self.recv():
                if action == "message":
                    print(data, flush=True)
                elif action == "error":
                    raise Exception(data)
                else:
                    response = input(data)
                    self.respond(response)

        except OSError:
            print("Game over!")

if __name__ == "__main__":
    hostpair = ("localhost", 5555)
    name = "Henry"

    Client(hostpair, name).run()
