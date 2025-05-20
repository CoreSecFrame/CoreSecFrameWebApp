#!/bin/bash
# setup.sh

# Set colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CoreSecFrame Web Interface Setup ===${NC}"
echo "This script will set up the CoreSecFrame Web Interface."

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo -e "${YELLOW}Detected Python version: ${python_version}${NC}"
required_version="3.8.0"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Python version must be at least 3.8.0${NC}"
    exit 1
fi

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}tmux is not installed. Installing...${NC}"
    sudo apt-get update
    sudo apt-get install -y tmux
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install tmux${NC}"
        exit 1
    fi
    echo -e "${GREEN}tmux installed successfully${NC}"
else
    echo -e "${GREEN}tmux is already installed${NC}"
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create virtual environment${NC}"
    exit 1
fi
echo -e "${GREEN}Virtual environment created${NC}"

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to activate virtual environment${NC}"
    exit 1
fi
echo -e "${GREEN}Virtual environment activated${NC}"

# Install dependencies with specific versions
echo -e "${YELLOW}Installing dependencies with specific versions...${NC}"
pip install --upgrade pip
pip uninstall -y flask flask-login werkzeug flask-sqlalchemy flask-migrate flask-wtf
pip install werkzeug==2.2.3
pip install flask==2.2.5
pip install flask-login==0.6.2
pip install flask-sqlalchemy==3.0.3
pip install flask-migrate==4.0.4
pip install flask-wtf==1.1.1
pip install flask-socketio==5.3.4
pip install python-socketio==5.8.0
pip install eventlet==0.33.3
pip install gunicorn==21.2.0
pip install psutil==5.9.5
pip install paramiko==3.1.0
pip install requests==2.31.0
pip install email-validator==2.0.0
pip install python-dotenv==1.0.0

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install dependencies${NC}"
    exit 1
fi
echo -e "${GREEN}Dependencies installed${NC}"

# Set Flask app environment variable
export FLASK_APP=run.py
echo -e "${YELLOW}Set FLASK_APP environment variable to run.py${NC}"

# Create required directories
echo -e "${YELLOW}Creating required directories...${NC}"
mkdir -p logs modules instance
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create directories${NC}"
    exit 1
fi
echo -e "${GREEN}Directories created${NC}"

# Initialize database manually since we're having issues with Flask-Migrate
echo -e "${YELLOW}Initializing database manually...${NC}"
python -c "
from app import create_app, db
from app.auth.models import User
app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to initialize database${NC}"
    exit 1
fi
echo -e "${GREEN}Database initialized${NC}"

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod -R 755 .
chmod -R 777 logs modules instance 
if [ -f app.db ]; then
    chmod 777 app.db
fi
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to set permissions${NC}"
    exit 1
fi
echo -e "${GREEN}Permissions set${NC}"

# Create admin user
echo -e "${YELLOW}Creating admin user...${NC}"
python -c "
from app import create_app, db
from app.auth.models import User
from datetime import datetime
app = create_app()
with app.app_context():
    # Check if admin user already exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print('Creating admin user...')
        admin = User(
            username='admin',
            email='admin@example.com',
            role='admin',
            created_at=datetime.utcnow()
        )
        admin.set_password('admin')  # Set a default password
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully.')
    else:
        print('Admin user already exists.')
"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create admin user${NC}"
    exit 1
fi
echo -e "${GREEN}Admin user created${NC}"

# Done
echo -e "${GREEN}=== Setup completed successfully ===${NC}"
echo -e "${YELLOW}You can now run the application with:${NC}"
echo -e "${GREEN}source venv/bin/activate${NC}"
echo -e "${GREEN}export FLASK_APP=run.py${NC}"
echo -e "${GREEN}flask run --host=0.0.0.0${NC}"
echo -e "${YELLOW}Or using Docker:${NC}"
echo -e "${GREEN}docker-compose up -d${NC}"