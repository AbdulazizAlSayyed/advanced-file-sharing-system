import socket
import threading
import os
import hashlib
from datetime import datetime



HOST = '10.21.134.17'
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().strftime("%Y-%m-%d")  # Example: 2025-04-26

    # Determine the log type
    lower_msg = message.lower()
    if "error" in lower_msg or "failed" in lower_msg or "❌" in lower_msg:
        log_file = os.path.join(LOG_DIR, f'error_log_{today_date}.txt')
    elif "warning" in lower_msg or "high memory" in lower_msg or "overload" in lower_msg:
        log_file = os.path.join(LOG_DIR, f'warning_log_{today_date}.txt')
    else:
        log_file = os.path.join(LOG_DIR, f'info_log_{today_date}.txt')
    
    # Write the log
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")


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
    filename = parts[1]
    filesize = int(parts[2])
    client_hash = parts[3]
    
    filepath = os.path.join(FILES_DIR, filename)

    if os.path.exists(filepath):
        conn.send("FILE_EXISTS".encode())   # 🔥 tell client file already exists

        user_decision = conn.recv(1024).decode()  # wait for client choice
        if user_decision.upper() == "NEW_VERSION":
            filename = generate_versioned_filename(FILES_DIR, filename)
            filepath = os.path.join(FILES_DIR, filename)
            conn.send(f"NEW_FILENAME {filename}".encode())
        else:
            conn.send(f"OVERWRITE {filename}".encode())
    else:
        conn.send("NO_FILE_EXISTS".encode())

    # Now ready to receive the file
    conn.send("READY_REC".encode())

    chunk_size = 1024
    with open(filepath, 'wb') as f:
        bytes_received = 0
        while bytes_received < filesize:
            chunk = conn.recv(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    log(f"File received: {filename} from {addr}")

    server_hash = compute_sha256(filepath)
    if server_hash == client_hash:
        log(f"Hash match for {filename} ok")
    else:
        log(f"Hash mismatch for {filename} ❌ Possible corruption")

def download_file_handler(conn, cmd_parts, addr):
    filename = cmd_parts[1]
    if len(cmd_parts) >= 3:
        already_have = int(cmd_parts[2])
    else:
        already_have = 0
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
                f.seek(already_have)  # 🛑 Skip already downloaded part
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    conn.sendall(chunk)
        log(f"Sent {filename} to {addr}")
    else:
        conn.send("ERROR FILE NOT FOUND".encode())
        log(f"ERROR FILE NOT FOUND: {filename} requested by {addr}")

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
    server.settimeout(1.0)  # Very important!

    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
    log("Server started and listening for connections")

    try:
        running = True
        while running:
            try:
                conn, addr = server.accept()
                thread = threading.Thread(target=handle_client, args=(conn, addr))
                thread.start()
            except socket.timeout:
                continue  # No connection, just retry
    except KeyboardInterrupt:
        print("\n[SERVER SHUTDOWN] Stopping server...")
        log("Server shutdown manually by KeyboardInterrupt")
        running = False
    except Exception as e:
        log(f"Server error: {e}")
    finally:
        server.close()
        print("[SERVER CLOSED]")
        log("Server socket closed.")

if __name__ == "__main__":
    main()