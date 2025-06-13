from functools import wraps
from flask import flash, redirect, url_for, current_app, request, jsonify # Added jsonify
from flask_login import current_user
# Assuming log_security_event is accessible.
from app.core.logging import log_security_event

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated and has the is_admin attribute/method
        is_admin_check = False
        if current_user.is_authenticated:
            if hasattr(current_user, 'is_admin') and callable(current_user.is_admin):
                is_admin_check = current_user.is_admin()
            elif hasattr(current_user, 'is_admin'): # Treat as property if not callable
                is_admin_check = current_user.is_admin

        if not is_admin_check:
            # Log the security event
            log_security_event(
                message=f"Unauthorized access attempt to admin route {request.path} by user {current_user.username if current_user.is_authenticated else 'anonymous'}.",
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr,
                level="warning"
            )

            # Check if the request prefers a JSON response
            # Simpler check for typical API scenarios:
            # request.is_json is True if mimetype is application/json
            # request.accept_mimetypes.best_match checks if 'application/json' is acceptable by the client
            if request.is_json or \
               request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json' and \
               request.accept_mimetypes['application/json'] > request.accept_mimetypes.get('text/html', 0):
                return jsonify(status='error', message='Forbidden: Administrator access required.'), 403
            else:
                flash('You do not have permission to access this page. Administrator privileges are required.', 'danger')
                return redirect(url_for('core.index'))
        return f(*args, **kwargs)
    return decorated_function

def json_success(data=None, message=None, status_code=200):
    response = {'status': 'success'}
    if message:
        response['message'] = message
    if data is not None: # Allow data to be an empty list or dict, or False, 0, etc.
        response['data'] = data
    return jsonify(response), status_code

def json_error(message, error_code=None, status_code=400, details=None):
    response = {'status': 'error', 'message': message}
    if error_code:
        response['error_code'] = error_code
    if details: # Allow details to be an empty list or dict
        response['details'] = details
    return jsonify(response), status_code
