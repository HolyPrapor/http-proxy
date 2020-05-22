import argparse
import re
import signal
import socket
import sys
import threading

HOST_NAME = "127.0.0.1"
BIND_PORT = 12345
MAX_REQUEST_LEN = 1024
CONNECTION_TIMEOUT = 5

VERBOSE = False
filters = "filters.txt"


def handle_browser_request(connection_socket):
    request = connection_socket.recv(MAX_REQUEST_LEN).decode('utf8')

    if not len(request):
        return

    url, webserver, port = extract_config_from_request(request)

    with open(filters, 'r') as f:
        for line in filter(lambda x: len(x), f.readlines()):
            if re.findall(rf'{line.rstrip()}', url):
                connection_socket.sendall("HTTP/1.1 403 "
                                          "Forbidden\r\nConnection: "
                                          "Closed\r\n".encode('utf8'))
                return

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(CONNECTION_TIMEOUT)
    try:
        s.connect((webserver, port))
        s.sendall(request.encode('utf8'))
    except socket.error:
        connection_socket.sendall(b'')
        return

    data = b''
    buffer = b'stub'
    while len(buffer):
        buffer = s.recv(MAX_REQUEST_LEN)
        data += buffer
    connection_socket.sendall(data)


def extract_config_from_request(request):
    first_line = request.split('\n')[0]
    splitted_line = first_line.split(' ')
    request_type = splitted_line[0]

    url = splitted_line[1]

    if VERBOSE:
        print(request_type, url)

    http_pos = url.find("://")
    if http_pos == -1:
        rest_of_url = url
    else:
        rest_of_url = url[(http_pos + 3):]

    port_pos = rest_of_url.find(":")

    webserver_pos = rest_of_url.find("/")
    if webserver_pos == -1:
        webserver_pos = len(rest_of_url)

    if port_pos == -1 or webserver_pos < port_pos:
        port = 80
        webserver = rest_of_url[:webserver_pos]
    else:
        port = int(
            (rest_of_url[(port_pos + 1):])[:webserver_pos - port_pos - 1])
        webserver = rest_of_url[:port_pos]
    return url, webserver, port


class Server:
    def __init__(self):
        signal.signal(signal.SIGINT, self.shutdown)
        self.serverSocket = socket.socket(socket.AF_INET,
                                          socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind((HOST_NAME, BIND_PORT))
        self.serverSocket.listen(10)
        self.clients = []

    def listen_for_client(self):
        while True:
            (clientSocket,
             client_address) = self.serverSocket.accept()

            self.clients.append(clientSocket)

            threading.Thread(target=handle_browser_request,
                             args=(clientSocket,), daemon=True).start()

    def shutdown(self):
        for sock in self.clients:
            sock.close()
        self.serverSocket.close()
        sys.exit(0)


def parse_args(args):
    parser = argparse.ArgumentParser(description="Simple HTTP proxy\n")
    parser.add_argument('-p', '--port', action='store', type=int,
                        help='Proxy port. Default - 12345')
    parser.add_argument('-f', '--filters', action='store', type=str,
                        help='File with '
                             'adblocker '
                             'filters in '
                             'regex format '
                             'Default = '
                             'filters.txt')
    parser.add_argument('-v', '--verbose', action='store_true')

    parsed = parser.parse_args(args)

    if parsed.port and (parsed.port < 0 or parsed.port > 65535):
        print("Please provide correct port.")
        exit(1)

    return parsed


def main(args):
    args = parse_args(args[1:])
    if args.verbose:
        global VERBOSE
        VERBOSE = True

    if args.port:
        global BIND_PORT
        BIND_PORT = args.port

    if args.filters:
        global filters
        filters = args.filters
    print("HTTP Proxy is starting.")
    server = Server()
    server.listen_for_client()


if __name__ == "__main__":
    main(sys.argv)
