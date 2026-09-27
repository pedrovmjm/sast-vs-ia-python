# ThreatByte

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Available-blue)](https://www.docker.com/)

![OpenGrep SAST](https://github.com/anotherik/ThreatByte/actions/workflows/sast-opengrep.yml/badge.svg?branch=main)
![Trivy SCA](https://github.com/anotherik/ThreatByte/actions/workflows/sca-trivy.yml/badge.svg?branch=main)
![KICS IaC Scan](https://github.com/anotherik/ThreatByte/actions/workflows/iac-kics.yml/badge.svg?branch=main)
![ZAP DAST Scan](https://github.com/anotherik/ThreatByte/actions/workflows/dast-zap.yml/badge.svg?branch=main)


ThreatByte is a deliberately vulnerable web application designed to demonstrate some Web and API security risks. It serves as a learning platform for security professionals and developers to explore common vulnerabilities in a controlled environment.

## 🚀 Features

The ThreatByte application aims to represent a simple online file-storing and sharing platform. It is developed in Python and uses the Flask framework. Currently it has the following features:

- **User Authentication:** Users can sign up, log in, and log out.
- **Dashboard:** Users have a personalized dashboard to view and manage their uploaded files.
- **File Upload:** Users can upload files to the application.
- **File Download:** Users can download files from the application.
- **Profile Management:** Users can view and edit their profile information.

## ⚠️ Vulnerabilities Overview

- Insecure Configurations
- Weak or Improper Cryptographic Implementations
- Lack of Brute-Force Protection
- Weak Session Management
- Broken Object Level Authorization (BOLA)
- Broken Object Property Level Authorization (BOPA)
- Broken Function Level Authorization (BFLA)
- Cross-Site Request Forgery (CSRF)
- Path Traversal
- SQL Injection
- Cross-Site Scripting (XSS):
  - Reflected XSS
  - Stored XSS
  - DOM-based XSS
- Unrestricted File Upload
- Server-Side Request Forgery (SSRF)

## 🛠️ Requirements

- Python 3.x (where x is your specific Python version)
- SQLite

## 🖥️ Running ThreatByte Locally

```sh
# Clone repository
git clone https://github.com/anotherik/ThreatByte.git && cd ThreatByte

# Create and activate virtual environment
python -m venv venv_threatbyte
source venv_threatbyte/bin/activate  # macOS/Linux
venv_threatbyte\Scripts\activate     # Windows

# Install dependencies and setup database
pip install -r requirements.txt
python db/create_db_tables.py

# Run the application
python run.py

# Open in browser: http://localhost:5000

# When finished, deactivate the virtual environment
deactivate
```

## 📦 Running with Containers (Docker or Podman)

```sh
# Build the image
docker build -t threatbyte .
# or (with Podman)
podman build -t threatbyte .

# Run the container
docker run -p 5000:5000 threatbyte
# or (with Podman)
podman run -p 5000:5000 threatbyte
````

## 🤝 Contributing

Contributions are welcomed! Please fork the repository and create a pull request with your changes. You can also contribute by reporting issues, suggesting improvements, or providing feedback through comments. Whether it's refining documentation, optimizing code, or contributing new vulnerabilities or weaknesses to enhance the application's scope, all contributions are valuable!

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

