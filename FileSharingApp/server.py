import socket
import threading
import os
import hashlib
from datetime import datetime

HOST = '10.21.146.204'
PORT = 5050

FILES_DIR = 'files'
LOG_DIR = 'logs_server'
LOG_FILE = os.path.join(LOG_DIR, 'server_log.txt')

os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"[{datetime.now()}] Server log file created\n")

def log(message):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def compute_sha256(filepath):
    sha256 = hashlib.sha256() #Creates a new SHA-256 hash object using Python’s built-in hashlib module.
    #f.read(4096): reads the next 4096 bytes from the file
    #lambda: f.read(4096): wraps that call in a no-argument function
    #iter(lambda..., b""): keeps calling that lambda until it returns b"" (an empty byte string), which means end of file
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):       #This is a clever and efficient way to read the file in chunks of 4096 bytes (4 KB) until the end.
            sha256.update(chunk)    #Each chunk is fed into the SHA-256 object to incrementally build the hash.
    return sha256.hexdigest()   #After the whole file is processed, this returns the final hash value as a hex string (e.g., '972bb2...d8d9597c0').

def generate_versioned_filename(directory, filename):
    name, ext = os.path.splitext(filename)
    version = 1
    new_filename = filename
    while os.path.exists(os.path.join(directory, new_filename)):
        version += 1
        new_filename = f"{name}_v{version}{ext}"
    return new_filename

def handle_upload(conn, parts, addr): 
    filename = parts[1]                  # e.g., "test0.txt"
    filesize = int(parts[2])             # e.g., 144
    client_hash = parts[3]     #1 Transfer Corruption Prevention         # hash sent by client

   # This ensures no overwrite — adds _v2 if needed
    filename = generate_versioned_filename(FILES_DIR, filename)
    filepath = os.path.join(FILES_DIR, filename)

# Tell client server is ready
    conn.send("READY_REC".encode())

    # Receive file in chunks and save it
    chunk_size = 1024
    with open(filepath, 'wb') as f:
        bytes_received = 0
        while bytes_received < filesize:
            chunk = conn.recv(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    log(f"File received: {filename} from {addr}")# Log successful reception
    # Server computes SHA-256 hash of the received file
    server_hash = compute_sha256(filepath) #1Transfer Corruption Prevention
        
    # Compare server's hash to what the client sent
    if server_hash == client_hash:  #1 Transfer Corruption Prevention     #After receiving the file, the server recomputes the hash using the same method, and checks:
        log(f"Hash match for {filename} ok")
    else:
        log(f"Hash mismatch for {filename} ❌ Possible corruption")

def download_file_handler(conn, cmd_parts, addr):
    filename = cmd_parts[1]
    filepath = f"{FILES_DIR}/{filename}"

    if os.path.exists(filepath):
        filehash = compute_sha256(filepath) #2. Storage Corruption Prevention        #  Calculate file hash
        conn.send(filehash.encode())  #  Send hash first
        ack = conn.recv(1024).decode()
        if ack != "HASH_RECEIVED":
            log(f"Client did not acknowledge hash, download aborted.")
            return

#Then send file size
        size = os.path.getsize(filepath)            
        conn.send(f"{size}".encode())

        recv_ack = conn.recv(1024)
        if recv_ack == b"READY_TO_REC":
            with open(filepath, 'rb') as f:
                conn.sendfile(f)
        log(f"Sent {filename} to {addr}")
    else:
        conn.send("ERROR FILE NOT FOUND".encode())

def handle_list(conn):
    files = os.listdir(FILES_DIR)
    conn.send("ACK_LIST".encode())
    if conn.recv(1024).decode() != "READY_FOR_LIST":
        return
    if not files:
        conn.send("No files available.".encode())
    else:
        conn.send('\n'.join(files).encode())

def handle_client(conn, addr):
    log(f"New client connected from {addr}")
    try:
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

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
    log("Server started and listening for connections")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    main()
