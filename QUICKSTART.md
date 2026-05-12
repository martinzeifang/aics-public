# 🚀 Quick Start Guide

Get the development environment running in 5 minutes!

## Prerequisites

- **Windows, Linux, or macOS**
- **Sudo access** (for system package installation on Linux)

## Setup (One-Time)

### Option 1: Automatic Setup (Recommended)

#### Linux / macOS
```bash
./setup-dev.sh
```

#### Windows
```batch
setup-dev.bat
```

The script will:
✅ Install system dependencies (Python, Node.js)  
✅ Create Python virtual environment  
✅ Install all Python packages  
✅ Install all npm packages  
✅ Verify everything works  

### Option 2: Manual Setup

#### Linux / macOS
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.12-venv python3-full nodejs npm

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Install frontend packages
cd frontend
npm install
cd ..
```

#### Windows
```batch
# Create virtual environment
python -m venv venv
venv\Scripts\activate.bat

# Install Python packages
pip install -r requirements.txt

# Install frontend packages
cd frontend
npm install
cd ..
```

## Start Development Servers

### Option 1: Automatic Start

#### Linux / macOS
```bash
./start-dev.sh
```

#### Windows
```batch
start-dev.bat
```

### Option 2: Manual Start (in separate terminals)

#### Terminal 1: Backend (HTTPS)
```bash
# Linux/macOS
source venv/bin/activate
python run_dev.py

# Windows
venv\Scripts\activate.bat
python run_dev.py
```

#### Terminal 2: Frontend
```bash
cd frontend
npm run dev
```

## 🎯 Access Points

| Component | URL | Notes |
|-----------|-----|-------|
| **Web UI** | http://localhost:5173 | Vue.js frontend |
| **API** | https://localhost:5000 | Flask backend |
| **Health** | https://localhost:5000/health | Health check |
| **Swagger** | https://localhost:5000/api/docs/swagger.json | API docs |

## 🔐 Demo Credentials

| User | Email | Password |
|------|-------|----------|
| Admin | admin@example.com | admin-password |
| Editor | editor@example.com | editor-password |

## ⚠️ HTTPS Certificate Warning

The backend runs on HTTPS with a self-signed certificate.  
Your browser will show a warning - this is **expected and safe** in development.

**Chrome/Edge:** Click "Advanced" → "Proceed to localhost"  
**Firefox:** Click "Advanced..." → "Accept the Risk and Continue"  
**Safari:** Click "Show Details" → "Visit this website"

## 🛠️ Troubleshooting

### "Python not found"
- **Windows:** [Download Python 3.10+](https://www.python.org/downloads/) (check "Add Python to PATH")
- **Linux:** `sudo apt-get install python3.12 python3.12-venv`
- **macOS:** `brew install python@3.12`

### "Node.js not found"
- **Windows:** [Download Node.js 18+](https://nodejs.org/)
- **Linux:** `sudo apt-get install nodejs npm`
- **macOS:** `brew install node`

### "Module not found (Flask, etc)"
```bash
# Reactivate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate.bat  # Windows

# Reinstall requirements
pip install -r requirements.txt
```

### "Port 5000 already in use"
The backend runs on port 5000. If it's in use:
```bash
# Linux/macOS: Find and kill process
lsof -i :5000
kill -9 <PID>

# Windows: Find and kill process
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### "Port 5173 already in use"
The frontend runs on port 5173. Change it:
```bash
cd frontend
npm run dev -- --port 5174
```

## 📁 Project Structure

```
├── server/                 # Flask backend
│   ├── app.py             # App factory
│   ├── api/               # API endpoints
│   ├── auth/              # Authentication (LDAP, local)
│   └── ssl.py             # HTTPS certificate generation
│
├── frontend/              # Vue.js frontend
│   ├── src/               # Source code
│   ├── vite.config.ts     # Vite config
│   └── package.json       # npm dependencies
│
├── setup-dev.sh/bat       # Setup script
├── start-dev.sh/bat       # Start script
└── requirements.txt       # Python dependencies
```

## 🔒 Security Notes

- **HTTPS enabled by default** with auto-generated self-signed cert
- **JWT authentication** with 24-hour tokens
- **Rate limiting** on login (5 attempts per 5 minutes per IP)
- **CORS restricted** to localhost only in dev
- **LDAP/AD optional** for enterprise authentication

For production setup, see [docs/SECURITY_CONFIG.md](docs/SECURITY_CONFIG.md)

## 📚 Documentation

- **API Docs:** https://localhost:5000/api/docs/swagger.json
- **Setup Guide:** [docs/SECURITY_CONFIG.md](docs/SECURITY_CONFIG.md)
- **LDAP Integration:** [docs/LDAP_INTEGRATION.md](docs/LDAP_INTEGRATION.md)
- **Architecture:** [docs/ARCHITECTURE_DATABASE.md](docs/ARCHITECTURE_DATABASE.md)

## 🐛 Common Issues

### Hot Reload Not Working
The development servers support hot reload:
- **Backend:** Automatically restarts on code changes
- **Frontend:** Automatically reloads on file saves

If not working, restart the server.

### CORS Errors
Make sure:
- Frontend runs on http://localhost:5173
- Backend runs on https://localhost:5000
- Browser allows self-signed HTTPS cert

### LDAP Connection Issues
If you've enabled LDAP, verify:
- LDAP_ENABLED=true in environment
- LDAP server is reachable
- Service account credentials are correct

See [docs/LDAP_INTEGRATION.md](docs/LDAP_INTEGRATION.md) for troubleshooting.

## 🎓 Learning Resources

- [Vue.js 3 Guide](https://vuejs.org/guide/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [JWT Authentication](https://tools.ietf.org/html/rfc8949)
- [OWASP Security](https://owasp.org/www-project-top-ten/)

## 💡 Tips

### Debug Mode
```bash
# Enable SQL query logging
export SQL_ECHO=true
python run_dev.py
```

### Test LDAP Locally
```bash
# Install OpenLDAP for testing
sudo apt-get install slapd ldap-utils

# Or use Docker
docker run -d --name openldap -p 389:389 osixia/openldap
```

### View API Swagger
```
https://localhost:5000/api/docs/swagger.json
```

Open in [Swagger UI](https://swagger.io/tools/swagger-ui/) for interactive testing.

## 🚀 Next Steps

1. ✅ Run setup script
2. ✅ Start dev servers
3. ✅ Open http://localhost:5173
4. ✅ Login with demo credentials
5. ✅ Explore CRA module
6. ✅ Read [docs/ARCHITECTURE_DATABASE.md](docs/ARCHITECTURE_DATABASE.md)

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/martinzeifang/AI_Compliance_Suite/issues)
- **Docs:** [docs/](docs/)
- **Security:** [docs/SECURITY_CONFIG.md](docs/SECURITY_CONFIG.md)

---

**Ready?** Run:
```bash
./setup-dev.sh      # Linux/macOS
setup-dev.bat       # Windows
```

Then:
```bash
./start-dev.sh      # Linux/macOS
start-dev.bat       # Windows
```

Happy coding! 🎉
