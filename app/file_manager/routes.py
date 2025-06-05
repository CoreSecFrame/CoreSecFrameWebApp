# app/file_manager/routes.py - System-wide file manager
import os
import shutil
import mimetypes
import pwd
import grp
import stat
from datetime import datetime
from flask import render_template, request, jsonify, current_app, send_file, abort
from flask_login import login_required, current_user
from app.file_manager import bp
import werkzeug.utils

# Configuration for system access
ALLOWED_PATHS = [
    '/home',
    '/tmp',
    '/var/log',
    '/opt',
    '/usr/local',
    '/etc',  # Read-only for most users
    '/',      # Root access for admins
]

# Restricted paths that should never be accessible
RESTRICTED_PATHS = [
    '/proc',
    '/sys', 
    '/dev',
    '/run',
    '/boot',
    '/root',  # Unless user is admin
]

def is_admin_user():
    """Check if current user has admin privileges"""
    return current_user.is_authenticated and current_user.is_admin()

def is_path_allowed(path):
    """Check if the path is allowed for the current user"""
    abs_path = os.path.abspath(path)
    
    # Always deny restricted paths
    for restricted in RESTRICTED_PATHS:
        if abs_path.startswith(restricted):
            # Allow /root only for admins
            if restricted == '/root' and is_admin_user():
                continue
            return False
    
    # For non-admin users, restrict to allowed paths
    if not is_admin_user():
        # Allow user's home directory
        user_home = os.path.expanduser('~')
        if abs_path.startswith(user_home):
            return True
            
        # Check allowed paths
        for allowed in ALLOWED_PATHS[:-1]:  # Exclude root path for non-admins
            if abs_path.startswith(allowed):
                return True
        return False
    
    # Admins have broader access but still respect some restrictions
    return True

def get_safe_path(path):
    """Get a safe, absolute path and validate it"""
    if not path or path == '.':
        # Default starting path
        if is_admin_user():
            return '/'
        else:
            return os.path.expanduser('~')
    
    # Handle relative paths
    if not os.path.isabs(path):
        if is_admin_user():
            base = '/'
        else:
            base = os.path.expanduser('~')
        path = os.path.join(base, path)
    
    # Normalize the path
    path = os.path.abspath(path)
    
    # Check if path is allowed
    if not is_path_allowed(path):
        raise PermissionError(f"Access denied to path: {path}")
    
    return path

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

def get_file_permissions(file_path):
    """Get file permissions in human readable format"""
    try:
        st = os.stat(file_path)
        permissions = stat.filemode(st.st_mode)
        return permissions
    except (OSError, IOError):
        return "----------"

def get_file_owner(file_path):
    """Get file owner and group"""
    try:
        st = os.stat(file_path)
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except KeyError:
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            group = str(st.st_gid)
        return f"{owner}:{group}"
    except (OSError, IOError):
        return "unknown:unknown"

def get_file_info(file_path, relative_path=None):
    """Get detailed file information"""
    try:
        stat_info = os.stat(file_path)
        is_dir = os.path.isdir(file_path)
        
        return {
            'name': os.path.basename(file_path),
            'path': relative_path or file_path,
            'full_path': file_path,
            'is_dir': is_dir,
            'size': format_file_size(stat_info.st_size) if not is_dir else None,
            'size_bytes': stat_info.st_size if not is_dir else 0,
            'modified': datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'permissions': get_file_permissions(file_path),
            'owner': get_file_owner(file_path),
            'is_readable': os.access(file_path, os.R_OK),
            'is_writable': os.access(file_path, os.W_OK),
            'is_executable': os.access(file_path, os.X_OK),
            'is_hidden': os.path.basename(file_path).startswith('.')
        }
    except (OSError, IOError) as e:
        current_app.logger.warning(f"Error getting file info for {file_path}: {e}")
        return {
            'name': os.path.basename(file_path),
            'path': relative_path or file_path,
            'full_path': file_path,
            'is_dir': False,
            'size': None,
            'size_bytes': 0,
            'modified': None,
            'permissions': "----------",
            'owner': "unknown:unknown",
            'is_readable': False,
            'is_writable': False,
            'is_executable': False,
            'is_hidden': False,
            'error': str(e)
        }

@bp.route('/')
@login_required
def index():
    """File manager main page"""
    return list_files()

@bp.route('/list')
@login_required
def list_files_route():
    """Route for listing files"""
    return list_files()

def list_files(path=None):
    """List files and directories"""
    try:
        req_path = request.args.get('path', path)
        current_path = get_safe_path(req_path)

        if not os.path.exists(current_path):
            return render_template('file_manager/file_manager.html', 
                                 error=f"Path does not exist: {current_path}", 
                                 current_path=req_path or '/', 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager",
                                 is_admin=is_admin_user())

        if not os.path.isdir(current_path):
            return render_template('file_manager/file_manager.html', 
                                 error=f"Path is not a directory: {current_path}", 
                                 current_path=req_path or '/', 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager",
                                 is_admin=is_admin_user())

        # Check read permissions
        if not os.access(current_path, os.R_OK):
            return render_template('file_manager/file_manager.html', 
                                 error="Permission denied: Cannot read directory", 
                                 current_path=current_path, 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager",
                                 is_admin=is_admin_user())

        items = []
        show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
        
        try:
            # Get directory contents
            dir_contents = os.listdir(current_path)
            
            # Filter hidden files if not requested
            if not show_hidden:
                dir_contents = [item for item in dir_contents if not item.startswith('.')]
            
            # Sort: directories first, then files, both alphabetically
            dir_contents.sort(key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))
            
            for item in dir_contents:
                item_path = os.path.join(current_path, item)
                file_info = get_file_info(item_path, item_path)
                items.append(file_info)
                
        except PermissionError:
            return render_template('file_manager/file_manager.html', 
                                 error="Permission denied: Cannot access directory contents", 
                                 current_path=current_path, 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager",
                                 is_admin=is_admin_user())

        # Calculate parent directory
        parent_dir = None
        if current_path != '/':
            parent_dir = os.path.dirname(current_path)
            # Ensure parent is also allowed
            try:
                get_safe_path(parent_dir)
            except PermissionError:
                parent_dir = None

        # Log file manager access
        current_app.logger.info(
            f"File manager access: {current_path}",
            extra={
                'user_id': current_user.id,
                'path': current_path,
                'items_count': len(items),
                'is_admin': is_admin_user()
            }
        )

        return render_template('file_manager/file_manager.html', 
                             items=items, 
                             current_path=current_path, 
                             parent_dir=parent_dir,
                             show_hidden=show_hidden,
                             title="File Manager",
                             is_admin=is_admin_user())
                             
    except PermissionError as e:
        current_app.logger.warning(f"Permission denied in file manager: {e}", 
                                   extra={'user_id': current_user.id})
        return render_template('file_manager/file_manager.html', 
                             error=str(e), 
                             current_path='/', 
                             items=[], 
                             parent_dir=None,
                             title="File Manager",
                             is_admin=is_admin_user())
    except Exception as e:
        current_app.logger.error(f"Error in file manager: {e}", 
                                extra={'user_id': current_user.id})
        return render_template('file_manager/file_manager.html', 
                             error="An error occurred while accessing the file system.", 
                             current_path='/', 
                             items=[], 
                             parent_dir=None,
                             title="File Manager",
                             is_admin=is_admin_user())

@bp.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    """Create a new folder"""
    try:
        path = request.form.get('path', '/')
        folder_name = request.form.get('folder_name')

        if not folder_name:
            return jsonify(success=False, error="Folder name is required.")

        # Validate folder name
        secure_name = werkzeug.utils.secure_filename(folder_name)
        if not secure_name or secure_name != folder_name:
            return jsonify(success=False, error="Invalid folder name.")

        current_path = get_safe_path(path)
        new_folder_path = os.path.join(current_path, folder_name)

        # Check if we can write to the parent directory
        if not os.access(current_path, os.W_OK):
            return jsonify(success=False, error="Permission denied: Cannot write to directory.")

        if os.path.exists(new_folder_path):
            return jsonify(success=False, error="Folder already exists.")

        os.makedirs(new_folder_path)
        
        # Log folder creation
        current_app.logger.info(
            f"Folder created: {new_folder_path}",
            extra={'user_id': current_user.id, 'action': 'create_folder'}
        )
        
        return jsonify(success=True, message="Folder created successfully.")
        
    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error creating folder: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while creating the folder.")

@bp.route('/create_file', methods=['POST'])
@login_required
def create_file():
    """Create a new file"""
    try:
        path = request.form.get('path', '/')
        file_name = request.form.get('file_name')

        if not file_name:
            return jsonify(success=False, error="File name is required.")

        # Validate file name
        secure_name = werkzeug.utils.secure_filename(file_name)
        if not secure_name or secure_name != file_name:
            return jsonify(success=False, error="Invalid file name.")

        current_path = get_safe_path(path)
        new_file_path = os.path.join(current_path, file_name)

        # Check if we can write to the parent directory
        if not os.access(current_path, os.W_OK):
            return jsonify(success=False, error="Permission denied: Cannot write to directory.")

        if os.path.exists(new_file_path):
            return jsonify(success=False, error="File already exists.")

        # Create empty file
        with open(new_file_path, 'w') as f:
            f.write('')
            
        # Log file creation
        current_app.logger.info(
            f"File created: {new_file_path}",
            extra={'user_id': current_user.id, 'action': 'create_file'}
        )
        
        return jsonify(success=True, message="File created successfully.")
        
    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error creating file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while creating the file.")

@bp.route('/delete_item', methods=['POST'])
@login_required
def delete_item():
    """Delete a file or folder"""
    try:
        item_path = request.form.get('item_path')
        if not item_path:
            return jsonify(success=False, error="Item path is required.")

        full_path = get_safe_path(item_path)

        if not os.path.exists(full_path):
            return jsonify(success=False, error="Item not found.")

        # Check if we can write to the parent directory
        parent_dir = os.path.dirname(full_path)
        if not os.access(parent_dir, os.W_OK):
            return jsonify(success=False, error="Permission denied: Cannot delete from this directory.")

        # Additional safety check for important system directories
        if full_path in ['/', '/home', '/usr', '/var', '/etc', '/boot', '/sys', '/proc', '/dev']:
            return jsonify(success=False, error="Cannot delete system directories.")

        # Check if it's a directory or file
        is_directory = os.path.isdir(full_path)
        
        if is_directory:
            shutil.rmtree(full_path)
            action = "delete_folder"
        else:
            os.remove(full_path)
            action = "delete_file"
            
        # Log deletion
        current_app.logger.info(
            f"Item deleted: {full_path}",
            extra={'user_id': current_user.id, 'action': action, 'is_directory': is_directory}
        )

        return jsonify(success=True, message="Item deleted successfully.")
        
    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error deleting item {item_path}: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while deleting the item.")

@bp.route('/view_file')
@login_required
def view_file():
    """View file content"""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return jsonify(success=False, error="File path is required.")

        full_path = get_safe_path(file_path)

        if not os.path.exists(full_path):
            return jsonify(success=False, error="File not found.")

        if os.path.isdir(full_path):
            return jsonify(success=False, error="Cannot view directory content.")

        # Check read permissions
        if not os.access(full_path, os.R_OK):
            return jsonify(success=False, error="Permission denied: Cannot read file.")

        # Check file size (limit to 10MB for viewing)
        file_size = os.path.getsize(full_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify(success=False, error="File is too large to view (max 10MB).")

        # Try to read file content
        try:
            # Try UTF-8 first
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                # Try latin-1 as fallback
                with open(full_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except UnicodeDecodeError:
                return jsonify(success=False, error="File contains binary data and cannot be displayed as text.")

        # Log file view
        current_app.logger.info(
            f"File viewed: {full_path}",
            extra={'user_id': current_user.id, 'action': 'view_file', 'file_size': file_size}
        )

        return jsonify(success=True, content=content, size=format_file_size(file_size))

    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error viewing file {file_path}: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while reading the file.")

@bp.route('/download_file')
@login_required
def download_file():
    """Download a file"""
    try:
        file_path = request.args.get('path')
        if not file_path:
            abort(400, "File path is required.")

        full_path = get_safe_path(file_path)

        if not os.path.exists(full_path):
            abort(404, "File not found.")

        if os.path.isdir(full_path):
            abort(400, "Cannot download directory.")

        # Check read permissions
        if not os.access(full_path, os.R_OK):
            abort(403, "Permission denied: Cannot read file.")

        # Log file download
        current_app.logger.info(
            f"File downloaded: {full_path}",
            extra={'user_id': current_user.id, 'action': 'download_file'}
        )

        # Get MIME type
        mime_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'

        return send_file(
            full_path,
            as_attachment=True,
            download_name=os.path.basename(full_path),
            mimetype=mime_type
        )

    except PermissionError as e:
        abort(403, f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error downloading file {file_path}: {e}", extra={'user_id': current_user.id})
        abort(500, "An error occurred while downloading the file.")

@bp.route('/get_disk_usage')
@login_required
def get_disk_usage():
    """Get disk usage information for current directory"""
    try:
        path = request.args.get('path', '/')
        current_path = get_safe_path(path)
        
        total_size = 0
        file_count = 0
        folder_count = 0
        
        # Only calculate for readable directories
        if os.path.isdir(current_path) and os.access(current_path, os.R_OK):
            try:
                for root, dirs, files in os.walk(current_path):
                    # Skip if we can't read the directory
                    if not os.access(root, os.R_OK):
                        continue
                        
                    folder_count += len(dirs)
                    file_count += len(files)
                    
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            if os.access(file_path, os.R_OK):
                                total_size += os.path.getsize(file_path)
                        except (OSError, IOError):
                            continue  # Skip files we can't access
            except (OSError, IOError):
                pass  # Handle permission errors gracefully

        return jsonify({
            'success': True,
            'total_size': format_file_size(total_size),
            'total_size_bytes': total_size,
            'file_count': file_count,
            'folder_count': folder_count,
            'path': current_path
        })

    except Exception as e:
        current_app.logger.error(f"Error getting disk usage: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while calculating disk usage.")

@bp.route('/quick_navigate')
@login_required
def quick_navigate():
    """Get quick navigation shortcuts"""
    shortcuts = []
    
    # Always available shortcuts
    shortcuts.append({
        'name': 'Home',
        'path': os.path.expanduser('~'),
        'icon': 'house-door'
    })
    
    shortcuts.append({
        'name': 'Desktop',
        'path': os.path.expanduser('~/Desktop'),
        'icon': 'desktop'
    })
    
    shortcuts.append({
        'name': 'Documents',
        'path': os.path.expanduser('~/Documents'),
        'icon': 'folder'
    })
    
    shortcuts.append({
        'name': 'Downloads',
        'path': os.path.expanduser('~/Downloads'),
        'icon': 'download'
    })
    
    # Admin-only shortcuts
    if is_admin_user():
        shortcuts.extend([
            {
                'name': 'Root',
                'path': '/',
                'icon': 'hdd'
            },
            {
                'name': 'System Logs',
                'path': '/var/log',
                'icon': 'journal-text'
            },
            {
                'name': 'Configuration',
                'path': '/etc',
                'icon': 'gear'
            },
            {
                'name': 'Temporary',
                'path': '/tmp',
                'icon': 'clock'
            }
        ])
    
    # Filter shortcuts that actually exist and are accessible
    accessible_shortcuts = []
    for shortcut in shortcuts:
        try:
            path = get_safe_path(shortcut['path'])
            if os.path.exists(path) and os.access(path, os.R_OK):
                accessible_shortcuts.append(shortcut)
        except (PermissionError, OSError):
            continue
    
    return jsonify(shortcuts=accessible_shortcuts)

# Agregar esta función a app/file_manager/routes.py

@bp.route('/rename_item', methods=['POST'])
@login_required
def rename_item():
    """Rename a file or folder"""
    try:
        old_path = request.form.get('old_path')
        new_name = request.form.get('new_name')

        if not old_path or not new_name:
            return jsonify(success=False, error="Both old path and new name are required.")

        # Validate the old path
        old_full_path = get_safe_path(old_path)
        
        if not os.path.exists(old_full_path):
            return jsonify(success=False, error="Item not found.")

        # Secure the new name
        secure_new_name = werkzeug.utils.secure_filename(new_name)
        if not secure_new_name or secure_new_name != new_name:
            return jsonify(success=False, error="Invalid new name. Use only letters, numbers, hyphens, and underscores.")

        # Create new path
        parent_dir = os.path.dirname(old_full_path)
        new_full_path = os.path.join(parent_dir, new_name)

        # Check if we can write to the parent directory
        if not os.access(parent_dir, os.W_OK):
            return jsonify(success=False, error="Permission denied: Cannot rename in this directory.")

        # Validate the new path is also safe
        try:
            get_safe_path(new_full_path)
        except PermissionError:
            return jsonify(success=False, error="Permission denied: Invalid destination path.")

        if os.path.exists(new_full_path):
            return jsonify(success=False, error="An item with that name already exists.")

        # Rename the item
        os.rename(old_full_path, new_full_path)

        # Log rename action
        current_app.logger.info(
            f"Item renamed: {old_path} -> {new_full_path}",
            extra={'user_id': current_user.id, 'action': 'rename_item'}
        )

        return jsonify(success=True, message="Item renamed successfully.")

    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error renaming item: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while renaming the item.")

@bp.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    """Upload a file"""
    try:
        path = request.form.get('path', '/')
        
        if 'file' not in request.files:
            return jsonify(success=False, error="No file selected.")

        file = request.files['file']
        
        if file.filename == '':
            return jsonify(success=False, error="No file selected.")

        if file:
            # Secure the filename
            filename = werkzeug.utils.secure_filename(file.filename)
            if not filename:
                return jsonify(success=False, error="Invalid filename.")

            current_path = get_safe_path(path)
            full_path = os.path.join(current_path, filename)

            # Check if we can write to the directory
            if not os.access(current_path, os.W_OK):
                return jsonify(success=False, error="Permission denied: Cannot write to directory.")

            # Check if file already exists
            if os.path.exists(full_path):
                return jsonify(success=False, error="File already exists.")

            # Check file size (limit to 100MB)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > 100 * 1024 * 1024:  # 100MB
                return jsonify(success=False, error="File too large. Maximum size is 100MB.")

            # Save the file
            file.save(full_path)

            # Log file upload
            current_app.logger.info(
                f"File uploaded: {full_path} ({format_file_size(file_size)})",
                extra={'user_id': current_user.id, 'action': 'upload_file', 'filename': filename, 'file_size': file_size}
            )

            return jsonify(success=True, message="File uploaded successfully.")

    except PermissionError as e:
        return jsonify(success=False, error=f"Permission denied: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while uploading the file.")