import socket
import os
import sys
import time
from datetime import datetime

#client configuration
HOST = '10.21.175.130'
PORT = 5050

#directories for downloaded files and client logs
DOWNLOAD_DIR = 'received'
LOG_DIR = 'logs_client'
LOG_FILE = os.path.join(LOG_DIR, 'client_log.txt')

#ensure required client directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

#initialize client log file if not found
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"[{datetime.now()}] Client log file created\n")

#method used to log ibr 
def log(message):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {message}\n")

#method used to upload file to the server + tracking the progress ibr
def upload_file(sock, filepath):
    if not os.path.exists(filepath): #by default python will look into the working directory ibr 
        print(f"File not found: {filepath}")
        log(f"UPLOAD FAILED: File not found: {filepath}")
        return

    #getting the name of the file ibr 
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    log(f"Uploading file: {filename} ({filesize} bytes)")
    #sending the filename and the size of the file we want to upload to the server ibr 
    sock.send(f"UPLOAD {filename} {filesize}".encode())

# ✅ Fix: receive only once
    recv_ack = sock.recv(1024).decode()

#recieve ack from the server telling that the server is ready to recieve the file ibr 
    if recv_ack == "READY_REC":
        bytes_sent = 0
        chunk_size = 1024
        count_chunks_sent = 0

        with open(filepath, 'rb') as f:
            #while loop to send the file as chunks ibr 
            while bytes_sent < filesize:
                #read from the file a chuck of chunksize = to chunksize defined ibr
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                #sending the chucnk until size 1024 bytes ibr
                sock.sendall(chunk)
                bytes_sent += len(chunk)
                count_chunks_sent += 1


                #showing the progress ibr 
                percent = (bytes_sent / filesize) * 100
                sys.stdout.write(f"\rUploading: {percent:.2f}%")
                sys.stdout.flush()
                time.sleep(0.05)  # optional visual delay

        log(f"Upload complete: {filename}")
        print(f"\nUploaded {filename}")
    else:
        log(f"UPLOAD FAILED: Server not ready for {filename}")
        print("Server did not accept the upload request.")

#download file helper ibr
def download_file(sock, filename):
    #telling the server "I want to download file with filename if exists" ibr
    sock.send(f"DOWNLOAD {filename}".encode())
    size_data = sock.recv(1024).decode()

    #checking for file exitance form the server message ibr
    if size_data == "ERROR FILE NOT FOUND":
        print("The file does not exist on the server.")
        log(f"DOWNLOAD FAILED: {filename} not found on server")
        return

    #size is the expected size ibr
    filesize = int(size_data)
    sock.send("READY_TO_REC".encode()) #seding ack to the server informig it that the client is ready to recv ibr
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

            # this is for the progress bar ibr
            percent = (bytes_received / filesize) * 100
            sys.stdout.write(f"\rDownloading: {percent:.2f}%")
            sys.stdout.flush()
            time.sleep(0.05)

    log(f"Download complete: {filename}")
    print(f"\nDownloaded {filename}")

#method used to list the files available on the server ibr
def list_available_files(sock):
    sock.send("LIST".encode())
    if sock.recv(1024).decode() != "ACK_LIST":
        print("Unexpected server response.")
        return

    sock.send("READY_FOR_LIST".encode())
    #receive and print the files list ibr
    files = sock.recv(4096).decode()
    print("Files available on the server:\n" + files)
    log("Listed files on server")

#main function ibr
def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        log(f"Connected to server at {HOST}:{PORT}")
    except Exception as e:
        log(f"CONNECTION FAILED: {e}")
        print("Failed to connect to the server.")
        return

    # To allow the user make multiple manipulations  ibr
    while True:
        # to clean the input and remove the leading and ending space in the input use .strip() ibr
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

#entry point ibr
if __name__ == "__main__":
    main()
