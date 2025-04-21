import socket
import os
import sys
import time
import hashlib
from datetime import datetime

HOST = '10.21.146.204'
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
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def upload_file(sock, filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        log(f"UPLOAD FAILED: File not found: {filepath}")
        return

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    filehash = compute_sha256(filepath)     #This uses the full function we discussed earlier to compute a unique SHA-256 hash of the file.

    log(f"Uploading file: {filename} ({filesize} bytes) with SHA-256: {filehash}")
    sock.send(f"UPLOAD {filename} {filesize} {filehash}".encode())

    recv_ack = sock.recv(1024).decode()

    if recv_ack == "READY_REC":
        bytes_sent = 0
        chunk_size = 1024

        with open(filepath, 'rb') as f:
            while bytes_sent < filesize:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sock.sendall(chunk)
                bytes_sent += len(chunk)

                percent = (bytes_sent / filesize) * 100
                sys.stdout.write(f"\rUploading: {percent:.2f}%")
                sys.stdout.flush()
                time.sleep(0.05)

        log(f"Upload complete: {filename}")
        print(f"\nUploaded {filename}")
    else:
        log(f"UPLOAD FAILED: Server not ready for {filename}")
        print("Server did not accept the upload request.")

def download_file(sock, filename):
    sock.send(f"DOWNLOAD {filename}".encode())
    size_data = sock.recv(1024).decode()

    if size_data == "ERROR FILE NOT FOUND":
        print("The file does not exist on the server.")
        log(f"DOWNLOAD FAILED: {filename} not found on server")
        return

    filesize = int(size_data)
    sock.send("READY_TO_REC".encode())
    log(f"Downloading file: {filename} ({filesize} bytes)")

    filepath = os.path.join(DOWNLOAD_DIR, filename)
    bytes_received = 0
    chunk_size = 1024

    with open(filepath, 'wb') as f:
        while bytes_received < filesize:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

            percent = (bytes_received / filesize) * 100
            sys.stdout.write(f"\rDownloading: {percent:.2f}%")
            sys.stdout.flush()
            time.sleep(0.05)

    log(f"Download complete: {filename}")
    print(f"\nDownloaded {filename}")

def list_available_files(sock):
    sock.send("LIST".encode())
    if sock.recv(1024).decode() != "ACK_LIST":
        print("Unexpected server response.")
        return

    sock.send("READY_FOR_LIST".encode())
    files = sock.recv(4096).decode()
    print("Files available on the server:\n" + files)
    log("Listed files on server")

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
