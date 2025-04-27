# Advanced File Sharing System

## Overview
This project is an **Advanced File Sharing System** built using a multithreaded client-server architecture and a Flask-based web interface. It allows multiple clients to upload, download, and list files reliably over TCP sockets, ensuring file integrity with hashing mechanisms and maintaining detailed logging. 

The system emphasizes **scalability**, **reliability**, and **security**, forming a foundation for advanced features such as version control, access control, and resumable downloads.

---

## Features

### Core Functionalities
- **Multithreaded Server**: Handles multiple clients concurrently using TCP sockets.
- **File Upload and Download**: Secure file transfer operations with integrity verification (SHA-256 hashing).
- **File Listing**: Clients can list all available files.
- **Version Control**: Option to overwrite or create new versions of files automatically.
- **Resumable Downloads**: Supports continuing interrupted downloads.
- **Logging System**: Separate logging on both server and client, categorized into info, warning, and error logs.

### Web Interface (Flask)
- **User Authentication**: Login system with hashed passwords and role-based access control (admin/user).
- **Admin Features**:
  - View server logs
  - Delete server files
- **User Features**:
  - Upload, download, and list files
  - Logout securely
- **Progress Bar**: Visual feedback during file uploads.

---

## Technologies Used
- **Python**: Backend (Server and Client)
- **Socket Programming (TCP)**: Reliable client-server communication
- **Flask**: Web-based user interface
- **MySQL**: User authentication database
- **HTML & CSS**: Frontend for the web application
- **SHA-256 Hashing**: File integrity checks

---

## System Architecture
- **Server**: Listens for TCP connections, handles file operations, verifies integrity, and manages logging.
- **Client (CLI)**: Command-line tool to upload, download, and list files.
- **Client (Web)**: Flask-based frontend for file management and admin operations.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/advanced-file-sharing-system.git
cd advanced-file-sharing-system
```

### 2. Set up the Server
```bash
cd server
python server.py
```

### 3. Set up the Client (CLI)
```bash
cd client
python client.py
```

### 4. Set up the Web Interface (Flask App)
```bash
cd web
python app.py
```

### 5. Database Setup
- Create a MySQL database.
- Import the provided SQL script (if available) to set up user authentication tables.
- Update `config.py` with your database credentials.

### 6. Configuration
Modify `config.py` for:
- Server IP address
- Port numbers
- Database credentials

---

## Screenshots
- Login Page
- Admin Dashboard
- File Upload and Download
- File Version Conflict Handling
- Server Logs View (Admin Only)
- User Dashboard (Restricted Access)

*(Screenshots available in the `screenshots/` folder)*

---

## Challenges Faced
- Configuring the server for multi-device connections across the network.
- Handling file integrity across variable network conditions.
- Firewall port configuration to allow external access to the web server.
- Managing multithreaded synchronization for stable server performance.

---

## Team Members
- **Abdulaziz Al Sayyed**
- **Abdullah Jrad**
- **Ibrahim Mabrouki**
- **Sireen Hneini**

---

## Future Improvements
- Enhance the web UI design for a smoother experience.
- Implement a file search feature.
- Support advanced resumable downloads after network interruptions.
- Add encryption for file transfer security.

---

## Contact
- **Phone**: +961 70738343
- **Email**: abdulaziz.alsayyed@lau.edu

---

## License
This project is developed as part of the CSC430 – Computer Networks course at **Lebanese American University** under the supervision of **Dr. Louma Chaddad**.

---

## Acknowledgment
Thanks to all team members and our instructor for making this project a real-world learning experience!

---

> ✨ If you find this project helpful, feel free to star the repo and connect with us!
