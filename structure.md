CoreSecFrame-Web/
├── app/
│   ├── __init__.py               # Flask application initialization
│   ├── auth/                     # Authentication system
│   │   ├── __init__.py
│   │   ├── forms.py              # Login/registration forms
│   │   ├── models.py             # User model
│   │   ├── routes.py             # Auth routes
│   │   └── utils.py              # Auth utilities
│   ├── core/                     # Core framework functionality
│   │   ├── __init__.py
│   │   ├── models.py             # Data models
│   │   ├── routes.py             # Core routes
│   │   └── utils.py              # Utility functions
│   ├── modules/                  # Module management
│   │   ├── __init__.py
│   │   ├── routes.py             # Module routes
│   │   └── utils.py              # Module utilities
│   ├── sessions/                 # Session management
│   │   ├── __init__.py
│   │   ├── models.py             # Session models
│   │   ├── routes.py             # Session routes
│   │   └── utils.py              # Session utilities
│   ├── static/                   # Static files
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   ├── templates/                # Jinja2 templates
│   │   ├── auth/
│   │   ├── core/
│   │   ├── modules/
│   │   ├── sessions/
│   │   ├── base.html
│   │   └── index.html
│   ├── terminal/                 # Terminal/console implementation
│   │   ├── __init__.py
│   │   ├── routes.py             # Terminal routes
│   │   ├── socket.py             # WebSocket handlers
│   │   └── utils.py              # Terminal utilities
│   └── config.py                 # Application configuration
├── migrations/                   # Database migrations
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_core.py
│   ├── test_modules.py
│   └── test_sessions.py
├── .env                          # Environment variables
├── .gitignore
├── config.py                     # Configuration settings
├── requirements.txt              # Dependencies
├── run.py                        # Application entry point
└── README.md                     # Documentation