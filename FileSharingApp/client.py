import socket
import os
import sys
import time
import hashlib
from datetime import datetime

HOST = '10.21.134.83'
PORT = 5050

DOWNLOAD_DIR = 'received'
LOG_DIR = 'logs_client'
LOG_FILE = os.path.join(LOG_DIR, 'client_log.txt')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"[{datetime.now()}] Client log file created\n")

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
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def upload_file(sock, filepath, decision=None, progress_callback=None):  # Modified by Abdullah for Flask App
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        log(f"UPLOAD FAILED: File not found: {filepath}")
        return

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    filehash = compute_sha256(filepath)

    log(f"Uploading file: {filename} ({filesize} bytes) with SHA-256: {filehash}")
    sock.send(f"UPLOAD {filename} {filesize} {filehash}".encode())

    server_reply = sock.recv(1024).decode()

    if server_reply == "FILE_EXISTS":
        print(f"The file '{filename}' already exists on server.")
        if decision is None:  # Modified by Abdullah for Flask App
            decision = input("Type 'OVERWRITE' to replace or 'NEW_VERSION' to create new version: ").strip().upper()
        sock.send(decision.encode())


        server_reply = sock.recv(1024).decode()
        if server_reply.startswith("NEW_FILENAME"):
            _, new_name = server_reply.split(maxsplit=1)
            filename = new_name
            print(f"New file name: {filename}")
        else:
            print(f"Overwriting {filename} on server.")
    elif server_reply == "NO_FILE_EXISTS":
        pass  # No file conflict

    ready = sock.recv(1024).decode()
    if ready != "READY_REC":
        print("Server not ready.")
        return

    bytes_sent = 0
    chunk_size = 1024
    with open(filepath, 'rb') as f:
        while bytes_sent < filesize:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(chunk)
            bytes_sent += len(chunk)

            # if for flask pass the progress to the app
            if progress_callback:
                progress_callback(bytes_sent, filesize)
            else:
                #regular
                percent = (bytes_sent / filesize) * 100
                sys.stdout.write(f"\rUploading: {percent:.2f}%")
                sys.stdout.flush()
                time.sleep(0.01)
            
            # modified for flask app
            # percent = (bytes_sent / filesize) * 100
            # sys.stdout.write(f"\rUploading: {percent:.2f}%")
            # sys.stdout.flush()
            # time.sleep(0.01)

    log(f"Upload complete: {filename}")
    print(f"\nUploaded {filename}")

def download_file(sock, filename, existing_size=0, progress_callback=None): #modified by Abdullah for flask
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(filepath):
        existing_size = os.path.getsize(filepath)
    else:
        existing_size = 0

    sock.send(f"DOWNLOAD {filename} {existing_size}".encode())

    server_hash = sock.recv(1024).decode()  # receive server response (could be error)
    
    # 🛑 First check if it was an error
    if server_hash == "ERROR FILE NOT FOUND":
        print("The file does not exist on the server.")
        log(f"DOWNLOAD FAILED: {filename} not found on server")
        return  # ❗ immediately return without sending "HASH_RECEIVED"

    # ✅ Otherwise continue normally
    sock.send("HASH_RECEIVED".encode())  # send ack for hash

    size_data = sock.recv(1024).decode()

    filesize = int(size_data)
    sock.send("READY_TO_REC".encode())  # ack server to start sending file
    log(f"Downloading file: {filename} ({filesize} bytes)")

    filepath = os.path.join(DOWNLOAD_DIR, filename)

    bytes_received = 0
    chunk_size = 1024

    
    #with open(filepath, mode) as f:     #ab = append binary kant wb =write binary (so even if you downloaded 20% before, when you open it with 'wb', you erase the partial file)
    # modified by Abdullah for downloading from flask even if the file is in received directory server side
    if existing_size > 0:
        mode = 'ab'
    else:
        mode = 'wb'
    with open(filepath, mode) as f:
        while bytes_received < filesize:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

            # for flask
            if progress_callback:
                progress_callback(bytes_received, filesize)
            else:
                percent = (bytes_received / filesize) * 100
                sys.stdout.write(f"\rDownloading: {percent:.2f}%")
                sys.stdout.flush()
                time.sleep(0.01)

            # percent = (bytes_received / filesize) * 100
            # sys.stdout.write(f"\rDownloading: {percent:.2f}%")
            # sys.stdout.flush()
            # time.sleep(0.01)

    log(f"Download complete: {filename}")
    print(f"\nDownloaded {filename}")

    local_hash = compute_sha256(filepath)
    if local_hash == server_hash:
        log(f"Hash match after download: {filename}")
        print("✅ File verified successfully. ok")
    else:
        log(f"Hash mismatch after download: {filename}")
        print("❌ File may be corrupted. no")


def list_available_files(sock):
    sock.send("LIST".encode())
    if sock.recv(1024).decode() != "ACK_LIST":
        print("Unexpected server response.")
        return

    sock.send("READY_FOR_LIST".encode())
    data = sock.recv(4096).decode()
    print("Files available on the server:\n" + data)
    log("Listed files on server")
    return data.splitlines() #modified for flask

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        log(f"Connected to server at {HOST}:{PORT}")
    except Exception as e:
        log(f"CONNECTION FAILED: {e}")
        print("Failed to connect to the server.")
        return

    while True:
        cmd = input("\nCommands:\n- LIST\n- UPLOAD <filepath>\n- DOWNLOAD <filename>\n- EXIT\nEnter command: ").strip()

        if cmd.upper() == "LIST":
            log("Command: LIST")
            list_available_files(sock)

        elif cmd.upper().startswith("UPLOAD"):
            log(f"Command: {cmd}")
            parts = cmd.split(maxsplit=1)
            if len(parts) == 2:
                _, filepath = parts
                upload_file(sock, filepath)
            else:
                print("Invalid UPLOAD syntax. Usage: UPLOAD <filepath>")

        elif cmd.upper().startswith("DOWNLOAD"):
            log(f"Command: {cmd}")
            parts = cmd.split(maxsplit=1)
            if len(parts) == 2:
                _, filename = parts
                download_file(sock, filename)
            else:
                print("Invalid DOWNLOAD syntax. Usage: DOWNLOAD <filename>")

        elif cmd.upper() == "EXIT":
            log("Command: EXIT")
            break

        else:
            print("Invalid command. Try again.")

    sock.close()
    log("Connection closed.")

if __name__ == "__main__":
    main()