import argparse
import re
import signal
import socket
import sys
import threading
import select

HOST_NAME = "127.0.0.1"
BIND_PORT = 12345
MAX_BUFFER_SIZE = 65536
CONNECTION_TIMEOUT = 5

CONNECTION_ESTABLISHED_MESSAGE = b"HTTP/1.1 200 OK\r\n\r\n"
FORBIDDEN_MESSAGE = b"HTTP/1.1 403 Forbidden\r\n\r\n"
BAD_REQUEST_MESSAGE = b"HTTP/1.1 400 Bad Request\r\n\r\n"
INTERNAL_SERVER_ERROR = b"HTTP/1.1 501 Internal Server Error\r\n\r\n"

VERBOSE = False
filters = "filters.txt"


def handle_browser_request(connection_socket):
    connection_socket.settimeout(CONNECTION_TIMEOUT)
    request = read_all(connection_socket)
    # print("=> " + request.decode('utf8'))

    if not len(request):
        return

    url, webserver, port, request_type = extract_config_from_request(request)

    if is_url_filtered(url):
        connection_socket.sendall(FORBIDDEN_MESSAGE)
        connection_socket.close()
        return

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(CONNECTION_TIMEOUT)
    try:
        s.connect((webserver, port))
    except socket.error:
        connection_socket.sendall(BAD_REQUEST_MESSAGE)
        connection_socket.close()
        return

    if request_type == "CONNECT":
        connection_socket.sendall(CONNECTION_ESTABLISHED_MESSAGE)
        handle_request_response_exchange(connection_socket, s)
    elif request_type == "GET" or request_type == "POST":
        s.sendall(request)
        handle_request_response_exchange(connection_socket, s)
    else:
        # Not Implemented
        connection_socket.sendall(INTERNAL_SERVER_ERROR)
        s.close()
        connection_socket.close()
        return


def handle_request_response_exchange(client_socket, server_socket):
    cur_sockets = [server_socket, client_socket]
    while True:
        ready_read, ready_write, errors = select.select(cur_sockets,
                                                        [],
                                                        cur_sockets,
                                                        CONNECTION_TIMEOUT)
        if not len(ready_read):
            server_socket.close()
            client_socket.close()
            return

        for sock in ready_read:
            data = read_all(sock)

            if not len(data):
                cur_sockets.remove(sock)
                sock.close()
                continue
            if sock is server_socket:
                if VERBOSE:
                    print(f"<= [{len(data)}]")
                client_socket.sendall(data)
            else:
                if VERBOSE:
                    print(f"=> [{len(data)}]")
                server_socket.sendall(data)


def is_url_filtered(url):
    with open(filters, 'r') as f:
        for line in filter(lambda x: len(x), f.readlines()):
            if re.findall(rf'{line.rstrip()}', url):
                return True
    return False


def read_all(sock):
    # data = b''
    # buffer = b'stub'
    # while len(buffer):
    #     try:
    #         buffer = sock.recv(MAX_BUFFER_SIZE)
    #     except socket.error:
    #         break
    #     data += buffer
    # return data
    # The code above doesn't work and I don't know why actually
    try:
        return sock.recv(MAX_BUFFER_SIZE)
    except:
        # print("ERROR WHILE READING SOCKET")
        return b''


def extract_config_from_request(request):
    splitted_request = request.decode('utf8').split('\n')
    first_line = splitted_request[0]
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
    return url, webserver, port, request_type


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
            (client_socket,
             client_address) = self.serverSocket.accept()

            self.clients.append(client_socket)
            threading.Thread(target=handle_browser_request,
                             args=(client_socket,), daemon=True).start()

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


