import socket
import threading
import os
from datetime import datetime

#server configuration
HOST = '10.21.175.130'
PORT = 5050

#directories used for server file handling and logs
FILES_DIR = 'files'
LOG_DIR = 'logs_server'
LOG_FILE = os.path.join(LOG_DIR, 'server_log.txt')

#ensure server folders exist
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

#initialize server log file
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"[{datetime.now()}] Server log file created\n")

#method used to log messages with timestamps to the log file
def log(message):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def generate_versioned_filename(directory, filename):
    name, ext = os.path.splitext(filename)
    version = 1
    new_filename = filename

    while os.path.exists(os.path.join(directory, new_filename)):
        version += 1
        new_filename = f"{name}_v{version}{ext}"

    return new_filename

#upload file helper ibr
def handle_upload(conn, parts, addr): 
    filename = parts[1]
    filesize = int(parts[2])
    filename = generate_versioned_filename(FILES_DIR, filename)  # NEW LINE
    filepath = os.path.join(FILES_DIR, filename)

    #informing the client that server is ready to rec the file ibr
    conn.send("READY_REC".encode())

    
    chunk_size = 1024

    with open(filepath, 'wb') as f:
        bytes_received = 0
        count_chunks_recieved = 0
        #while loop to recieve the file as chunks ibr 
        while bytes_received < filesize:
            #recieving the chucnk until size 1024 bytes ibr
            chunk = conn.recv(chunk_size)
            if not chunk:
                break
            #writing the chunk in the created file of name filename ibr 
            f.write(chunk)
            bytes_received += len(chunk)
            count_chunks_recieved += 1

    log(f"File received: {filename} from {addr}")

#download file helper ibr
def download_file_handler(conn, cmd_parts, addr):
    #getting the file name
    filename = cmd_parts[1]
    #finding the file path
    filepath = f"{FILES_DIR}/{filename}"

    if os.path.exists(filepath):
        #getting the file size
        size = os.path.getsize(filepath)
        #sending the file size to the client to know what is the size expected to recieve
        conn.send(f"{size}".encode())
        #recv ack from the client indicating that the client is ready to recieve the file
        recv_ack = conn.recv(1024)
        if recv_ack == "READY_TO_REC".encode():
            with open(filepath, 'rb') as f:
                conn.sendfile(f)
        log(f"Sent {filename} to {addr}")
    else:
        #sending error if the file doesn't exist on server
        conn.send("ERROR FILE NOT FOUND".encode())

#list the availabel file in the server ibr 
def handle_list(conn):
    files = os.listdir(FILES_DIR)

    #checking for confirmation before sending the acutal ack ibr 
    conn.send("ACK_LIST".encode())
    if conn.recv(1024).decode() != "READY_FOR_LIST":
        return

    if not files:
        conn.send("No files available.".encode())
    else:
        conn.send('\n'.join(files).encode())

#handler method that will be called for each client seperattly ibr 
def handle_client(conn, addr):
    log(f"New client connected from {addr}")

    try:
        # listen to different and mulitple issued by the client 
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            parts = data.split()
            command = parts[0].upper()

            if command == "LIST":
                handle_list(conn)
            elif command == "UPLOAD":
                handle_upload(conn, parts, addr)
            elif command == "DOWNLOAD":
                download_file_handler(conn, parts, addr)
    except Exception as e:
        log(f"Error with client {addr}: {e}")
    finally:
        conn.close()
        log(f"Connection closed with {addr}")

#main function used to initialize the server socket and listen for connections ibr
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
    log("Server started and listening for connections")

    while True:
        conn, addr = server.accept()
        #creating a thread for each client inorder to handle them seperatly. ibr 
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    main()
