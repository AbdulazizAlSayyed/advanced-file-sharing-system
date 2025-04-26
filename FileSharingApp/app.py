from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql #this import is to connect to mysql
import socket
import hashlib
import os
import client #for using client.py
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SERVER_IP, SERVER_PORT #uses the global configuration

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Used to secure user sessions

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

# upload button in dashboard
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get the uploaded file
        uploaded_file = request.files['file']

        if uploaded_file.filename == '':
            flash('No selected file.', 'danger')
            return redirect(request.url)

        # temp save to upload then to the server
        filepath = os.path.join('temp', uploaded_file.filename)
        os.makedirs('temp', exist_ok=True)
        uploaded_file.save(filepath)

        try:
            #connection to the server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER_IP, SERVER_PORT))

            #upload command
            client.upload_file(sock, filepath, decision="OVERWRITE")

            sock.close()
            flash('File uploaded successfully!', 'success')

        except Exception as e:
            flash(f"Upload failed: {str(e)}", 'danger')

        finally:
            os.remove(filepath)  #temp file removed after succesfull upload

        return redirect(url_for('upload'))

    return render_template('upload.html')


if __name__ == '__main__':
    app.run(debug=True)
