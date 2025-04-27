from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql #this import is to connect to mysql
import socket
import hashlib
import os
import client #for using client.py
from client import list_available_files, download_file
import uuid
from threading import Thread
from flask import jsonify
from flask import send_file
from datetime import datetime
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SERVER_IP, SERVER_PORT #uses the global configuration

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Used to secure user sessions
upload_progress = {}
pending_uploads = {} #states as init then decision (overwrite or new) then upload
download_progress = {}
FILES_DIR = 'files'

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



# --------download----------

#download button in dashboard
@app.route('/download')
def download_form():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('download.html')

@app.route('/download_list')
def download_list():
    if 'username' not in session:
        return jsonify({'error':'not logged in'}), 403

    # # open a fresh socket and uses client method
    # sock = socket.socket()
    # sock.connect((SERVER_IP, SERVER_PORT))
    # files = list_available_files(sock)
    # sock.close()

    # return jsonify({'files': files})

    # works here because on the same laptop, otherwise needs change in the method to list files in server or client .py
    entries = []
    for name in os.listdir(FILES_DIR):
        path = os.path.join(FILES_DIR, name)
        if not os.path.isfile(path):
            continue
        st = os.stat(path)
        entries.append({
            'name':     name,
            'size':     st.st_size,
            'modified': datetime.fromtimestamp(st.st_mtime) \
                               .strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify({'files': entries})

@app.route('/download_init', methods=['POST'])
def download_init():
    if 'username' not in session:
        return jsonify({'error':'not logged in'}), 403

    filename = request.json.get('filename')
    local = os.path.join('received', filename)
    if os.path.exists(local):
        os.remove(local)

    sock = socket.socket()
    sock.connect((SERVER_IP, SERVER_PORT))

    # create an ID for tracking progress
    dl_id = str(uuid.uuid4())
    download_progress[dl_id] = 0

    def prog_cb(sent, total):
        download_progress[dl_id] = int((sent/total)*100)

    # client.download_file
    def bg():
        download_file(sock, filename, 0, prog_cb)
        download_progress[dl_id] = 100 # so the bar finishes if last integer was not 100
        sock.close()

    Thread(target=bg, daemon=True).start()
    return jsonify({'download_id': dl_id})

@app.route('/download_progress/<download_id>')
def get_download_progress(download_id):
    return jsonify({'percent': download_progress.get(download_id, 0)})

@app.route('/download_fetch/<filename>')
def download_fetch(filename):
    path = os.path.join('received', filename)
    if not os.path.exists(path):
        return "Not found", 404
    return send_file(path, as_attachment=True)


#----admin managing files

@app.route('/admin/files')
def admin_files():
    if session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    # # like in download to list the files
    # sock = socket.socket()
    # sock.connect((SERVER_IP, SERVER_PORT))
    # files = list_available_files(sock)
    # sock.close()

    # return render_template('manage_files.html', files=files)

    # smae as in download_list() because on same laptop
    entries = []
    for name in os.listdir(FILES_DIR):
        path = os.path.join(FILES_DIR, name)
        if not os.path.isfile(path):
            continue
        st = os.stat(path)
        entries.append({
            'name':     name,
            'size':     st.st_size,
            'modified': datetime.fromtimestamp(st.st_mtime) \
                               .strftime("%Y-%m-%d %H:%M:%S")
        })
    return render_template('manage_files.html', files=entries)

@app.route('/admin/delete_file', methods=['POST'])
def delete_file():
    if session.get('role') != 'admin':
        return jsonify({'error':'not allowed'}), 403

    filename = request.get_json().get('filename')
    if not filename:
        return jsonify({'error':'no filename'}), 400

    # same thing connect and use methods
    sock = socket.socket()
    sock.connect((SERVER_IP, SERVER_PORT))
    sock.send(f"DELETE {filename}".encode())
    resp = sock.recv(1024).decode()
    sock.close()

    if resp == "DELETED":
        return jsonify({'success': True})
    else:
        return jsonify({'error': resp}), 500


#by abdulaziz
# Register page handle
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'user')  # default role is 'user'

        # Hash the password
        hashed_password = hash_password(password)

        # Save user to database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if username already exists
        cursor.execute('SELECT * FROM users WHERE username=%s', (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        # Insert new user
        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)',
                       (username, hashed_password, role))
        conn.commit()
        conn.close()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logs')
def view_logs():
    if 'username' not in session or session.get('role') != 'admin':
        flash('Access denied. Admins only.', 'danger')
        return redirect(url_for('dashboard'))

    log_dir = 'logs_server'
    tree = {}

    # Build tree: {year: {month: {day: [files]}}}
    for year in sorted(os.listdir(log_dir)):
        year_path = os.path.join(log_dir, year)
        if not os.path.isdir(year_path):
            continue

        tree[year] = {}
        for month in sorted(os.listdir(year_path)):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue

            tree[year][month] = {}
            for day in sorted(os.listdir(month_path)):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue

                files = sorted(os.listdir(day_path))
                tree[year][month][day] = files

    return render_template('view_logs.html', tree=tree)



@app.route('/logs/read/<year>/<month>/<day>/<filename>')
def read_log(year, month, day, filename):
    if 'username' not in session or session.get('role') != 'admin':
        return "Access Denied", 403

    path = os.path.join('logs_server', year, month, day, filename)
    if not os.path.isfile(path):
        return "Log not found", 404

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    return content
#------------


if __name__ == '__main__':
    app.run(debug=True)
