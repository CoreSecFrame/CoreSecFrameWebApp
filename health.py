# Simple health check for Docker
from flask import Flask, jsonify

def add_health_check(app):
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': 'CoreSecFrame is running'
        }), 200
