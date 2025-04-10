import socket
import threading
import os
from datetime import datetime

HOST = '10.21.129.224'
PORT = 5050
FILES_DIR = 'files'
Server_DIR = 'logs_server'

os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(Server_DIR, exist_ok=True)
LOG_FILE = 'logs_server/server_log.txt'

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE,'w') as f:
        f.write(f"[{datetime.now()}] Server file created\n")

def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {msg}\n")


#upload file helper
def upload_file_handler(conn, cmd_parts, addr):
    filename = cmd_parts[1]
    size = int(cmd_parts[2])
    
    #informing the client that server is ready to rec the file
    conn.send("READY_REC".encode())

    with open(f"{FILES_DIR}/{filename}", 'wb') as f:

        bytes_received = 0
        count_chunks_recieved = 0

        #while loop to recieve the file as chunks
        while bytes_received < size:

            #recieving the chucnk until size 1024 bytes
            chunk = conn.recv(1024)
            if not chunk:
                break

            #writing the chunk in the created file of name filename
            f.write(chunk)
            bytes_received += len(chunk)
            count_chunks_recieved += 1

    log(f"Received {filename} from {addr}")


#download file helper 
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
        #rec
        recv_ack = conn.recv(1024)

        #recv ack from the client indicating that the client is ready to recieve the file
        if recv_ack == "READY_TO_REC".encode():
            with open(filepath, 'rb') as f:
                conn.sendfile(f)
        log(f"Sent {filename} to {addr}")
    else:
        conn.send("ERROR FILE NOT FOUND".encode())

#list the availabel file in the server
def list_avialable_files(conn):
    files = os.listdir(FILES_DIR)

    #checking for confirmation before sending the acutal ack
    conn.send("ACK_LIST".encode())

    rec_ack = conn.recv(1024).decode()
    if rec_ack != "READY_FOR_LIST":#Checking the confirmation
        return 
    
    if not files:
        conn.send("No files available.".encode())
    else:
        conn.send('\n'.join(files).encode())

#handler method that will be called for each client seperattly
def client_handler(conn, addr):
    log(f"Connected by {addr}")
    try:
        #
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            cmd_parts = data.split()
            command = cmd_parts[0]

            if command == "LIST":
                list_avialable_files(conn)

            elif command == "UPLOAD":
                upload_file_handler(conn, cmd_parts, addr)

            elif command == "DOWNLOAD":
                download_file_handler(conn, cmd_parts, addr)

    except Exception as e:
        log(f"Error with {addr}: {e}")
    finally:
        conn.close()

#main function
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        #creating a thread for each client inorder to handle them seperatly.
        threading.Thread(target=client_handler, args=(conn, addr)).start()

if __name__ == "__main__":
    main()
