from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql #this import is to connect to mysql
import socket
import hashlib
import os
import client #for using client.py
import uuid
from threading import Thread
from flask import jsonify
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SERVER_IP, SERVER_PORT #uses the global configuration

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Used to secure user sessions
upload_progress = {}
pending_uploads = {} #states as init then decision (overwrite or new) then upload

# Db connection
def get_db_connection():
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, port=3308) #port used by wamp's MySql on my laptop

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Login page handle
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hash_password(password)

        # Check user credentials in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=%s AND password_hash=%s', (username, hashed_password))
        user = cursor.fetchone()
        conn.close()

        # when correct save username and role in session
        if user:
            session['username'] = user[1]
            session['role'] = user[3]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect username or password.', 'danger')

    return render_template('login.html')

# Dashboard after login
@app.route('/dashboard')
def dashboard():
    if 'username' not in session: #for security if entered the dashboard without loggin in then go back to login page
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'])

# Logout user and clear session
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# updates the progress using a thread
def background_upload(upload_id):
    info = pending_uploads.pop(upload_id, None)
    if not info:
        return

    sock      = info['sock']
    filepath  = info['filepath']
    filesize  = os.path.getsize(filepath)
    bytes_sent = 0
    chunk_size = 1024

    # # progress gotten from client.py
    def prog_cb(sent, total):
        upload_progress[upload_id] = int((sent/total)*100)

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(chunk)
            bytes_sent += len(chunk)
            prog_cb(bytes_sent, filesize)

    upload_progress[upload_id] = 100
    sock.close()
    os.remove(filepath)

# upload button in dashboard
@app.route('/upload')
def upload_form():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('upload.html')

@app.route('/upload_init', methods=['POST'])
def upload_init():
    if 'username' not in session:
        return jsonify({'error': 'not logged in'}), 403

    # temp save to upload then to server
    # temp saving is needed here because in the client.py upload() it expects a path so from the website i get the file to flask then from temp to server using path
    f = request.files['file']
    if not f or f.filename == '':
        return jsonify({'error': 'no file'}), 400
    os.makedirs('temp', exist_ok=True)
    filepath = os.path.join('temp', f.filename)
    f.save(filepath)

    # connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, SERVER_PORT))

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    filehash = hashlib.sha256(open(filepath,'rb').read()).hexdigest()

    # send the UPLOAD command
    sock.send(f"UPLOAD {filename} {filesize} {filehash}".encode())
    server_reply = sock.recv(1024).decode()

    # 3) create an ID to track the progress
    upload_id = str(uuid.uuid4())
    pending_uploads[upload_id] = {
        'sock': sock,
        'filepath': filepath
    }

    if server_reply == 'FILE_EXISTS':
        # wait here for the client to choose
        return jsonify({'upload_id': upload_id, 'state': 'FILE_EXISTS'})
    elif server_reply == 'NO_FILE_EXISTS':
        ready = sock.recv(1024).decode()
        if ready != 'READY_REC':
            sock.close()
            return jsonify({'error': 'bad handshake'}), 500

        Thread(target=background_upload,
               args=(upload_id,),
               daemon=True).start()
        return jsonify({'upload_id': upload_id, 'state': 'STARTED'})
    else:
        sock.close()
        return jsonify({'error': 'unexpected reply'}), 500
    
@app.route('/upload_start', methods=['POST'])
def upload_start():
    data = request.get_json()
    upload_id = data.get('upload_id')
    decision = data.get('decision')  # "OVERWRITE" or "NEW_VERSION"
    info = pending_uploads.get(upload_id)
    if not info:
        return jsonify({'error':'unknown upload_id'}), 404

    sock = info['sock']
    filepath = info['filepath']

    # send the decision back to server
    sock.send(decision.encode())
    server_reply = sock.recv(1024).decode()

    # if NEW_FILENAME returned, rename the temp file
    if server_reply.startswith('NEW_FILENAME'):
        _, new_name = server_reply.split(maxsplit=1)
        new_path = os.path.join('temp', new_name)
        os.rename(filepath, new_path)
        info['filepath'] = new_path

    ready = sock.recv(1024).decode()
    if ready != 'READY_REC':
        sock.close()
        return jsonify({'error':'bad handshake'}), 500

    Thread(target=background_upload,
           args=(upload_id,),
           daemon=True).start()

    return jsonify({'state': 'STARTED'})


@app.route('/upload_progress/<upload_id>')
def get_upload_progress(upload_id):
    pct = upload_progress.get(upload_id, 0)
    return jsonify({'percent': pct})

if __name__ == '__main__':
    app.run(debug=True)
