import socket
import os
import sys
import time  # for testing
from datetime import datetime


HOST = '10.21.129.224'
PORT = 5050
DOWNLOAD_DIR = 'received'
Client_DIR= 'logs_client'

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(Client_DIR, exist_ok=True)

LOG_FILE = "logs_client/client_log.txt"
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE,'w') as f:
                f.write(f"[{datetime.now()}] Log_Client file is created\n")

#method used to log
def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {msg}\n")


#method used to upload file to the server + tracking the progress
def upload_file(sock, path):
    if not os.path.exists(path): #by default python will look into the working directory
        print(f"File not found: {path}")
        log(f"UPLOAD FAILED: File not found: {path}")
        return


    #getting the name of the file
    filename = os.path.basename(path)
    size = os.path.getsize(path)
    log(f"Uploading file: {filename} ({size} bytes)")

    #sending the filename and the size of the file we want to upload to the server
    sock.send(f"UPLOAD {filename} {size}".encode())

    recv_ack = sock.recv(1024)#recieve ack from the server telling that the server is ready to recieve the file

    if recv_ack == "READY_REC".encode():
        count_chunks_sent = 0
        with open(path, 'rb') as f:
            bytes_sent = 0
            chunck_size = 1024
            
            #while loop to send the file as chunks
            while bytes_sent < size:
                #read from the file a chuck of chunksize = to chunksize defined
                chunk = f.read(chunck_size)

                if not chunk:
                    break
                #sending the chucnk until size 1024 bytes
                sock.sendall(chunk)
                bytes_sent += len(chunk)

                count_chunks_sent += 1

                #showing the progress
                percent = (bytes_sent / size) * 100
                sys.stdout.write(f"\rUploading: {percent:.2f}%")
                sys.stdout.flush()

                time.sleep(0.1)
        log(f"Upload complete: {filename}")
        print(f"\nUploaded {filename}")
    else:
        log(f"UPLOAD FAILED: No READY respons from the server for {filename}")



def download_file(sock, filename):
    #telling the server "I want to download file with filename if exists"
    sock.send(f"DOWNLOAD {filename}".encode())

    #recieve the size of the file to know how much bytes expected to recieve
    size_data = sock.recv(1024)

    #checking for file exitance form the server message
    if size_data.decode() == "ERROR FILE NOT FOUND":
        print("File is not found on server.")
        log(f"DOWNLOAD FAILED: Server responded with error for {filename}")
        return

    #size is the expected size
    size = int(size_data.decode())

    sock.send("READY_TO_REC".encode())#seding ack to the server informig it that the client is ready to recv
    log(f"Downloading file: {filename} ({size} bytes)")

    with open(f"{DOWNLOAD_DIR}/{filename}", 'wb') as f:
        bytes_received = 0
        chunk_size = 1024 #size of the chucnk willing to recieve 
        count_chunks_recieved = 0
        while bytes_received < size:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break

            f.write(chunk)
            bytes_received += len(chunk)
            count_chunks_recieved += 1

            # this is for the progress bar
            percent = (bytes_received / size) * 100
            sys.stdout.write(f"\rDownloading: {percent:.2f}%")
            sys.stdout.flush()
            time.sleep(0.1)
        
    log(f"Download complete: {filename}")
    print(f"Downloaded {filename}")

#method used to list the files available on the server
def list_avialable_files(sock):
    sock.send("LIST".encode())

    rec_ack = sock.recv(1024).decode()
    if rec_ack != "ACK_LIST":
        print("Unexpected server response.")
        return
    
    sock.send("READY_FOR_LIST".encode())
    #receive and print the files list
    files_available =  sock.recv(4096).decode()
    print("Files Available os the server are:\n",files_available)
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
    
    # To allow the user make multiple manipulations 
    while True:
        # to clean the input and remove the leading and ending space in the input use .strip()
        cmd = input("Use the Following commands:\n(LIST, UPLOAD <file>, DOWNLOAD <file>, EXIT): ").strip()

        if cmd.upper() == "LIST":
            log("Command issued: LIST")
            list_avialable_files(sock)

        elif cmd.upper().startswith("UPLOAD"):
            log(f"Command issued: {cmd}")
            _, path = cmd.split(maxsplit=1)
            upload_file(sock, path)

        elif cmd.upper().startswith("DOWNLOAD"):
            log(f"Command issued: {cmd}")
            _, filename = cmd.split(maxsplit=1)
            download_file(sock, filename)

        elif cmd.upper() == "EXIT":
            log("Command issued: EXIT")
            break

    sock.close()
    log("Connection closed.")

if __name__ == "__main__":
    main()

