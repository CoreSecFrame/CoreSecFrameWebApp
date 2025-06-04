# app/file_manager/routes.py
import os
import shutil
import mimetypes
from datetime import datetime
from flask import render_template, request, jsonify, current_app, send_file, abort
from flask_login import login_required, current_user
from app.file_manager import bp
import werkzeug.utils

# Define a base directory for file operations.
# IMPORTANT: This should be configured securely in a real application.
BASE_WORKING_DIR_NAME = 'user_files'

def get_base_dir():
    """Get the base directory for file operations"""
    base_dir = os.path.join(current_app.instance_path, BASE_WORKING_DIR_NAME)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    return base_dir

def get_full_path(path):
    """Securely get full path and prevent directory traversal"""
    base_dir = get_base_dir()
    # Normalize and join the path
    full_path = os.path.normpath(os.path.join(base_dir, path))
    # Ensure the path is within the base directory
    if not full_path.startswith(base_dir):
        raise ValueError("Attempted access outside base directory.")
    return full_path

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

def get_file_info(file_path, relative_path):
    """Get detailed file information"""
    try:
        stat = os.stat(file_path)
        is_dir = os.path.isdir(file_path)
        
        return {
            'name': os.path.basename(file_path),
            'path': relative_path,
            'is_dir': is_dir,
            'size': format_file_size(stat.st_size) if not is_dir else None,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'permissions': oct(stat.st_mode)[-3:],
            'owner_readable': os.access(file_path, os.R_OK),
            'owner_writable': os.access(file_path, os.W_OK),
        }
    except (OSError, IOError) as e:
        current_app.logger.warning(f"Error getting file info for {file_path}: {e}")
        return {
            'name': os.path.basename(file_path),
            'path': relative_path,
            'is_dir': os.path.isdir(file_path),
            'size': None,
            'modified': None,
            'permissions': None,
            'owner_readable': False,
            'owner_writable': False,
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

def list_files(path="."):
    """List files and directories"""
    try:
        req_path = request.args.get('path', path)
        current_full_path = get_full_path(req_path)

        if not os.path.exists(current_full_path):
            return render_template('file_manager/file_manager.html', 
                                 error="Path does not exist.", 
                                 current_path=req_path, 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager")

        if not os.path.isdir(current_full_path):
            return render_template('file_manager/file_manager.html', 
                                 error="Path is not a directory.", 
                                 current_path=req_path, 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager")

        items = []
        try:
            for item in sorted(os.listdir(current_full_path), key=lambda x: (not os.path.isdir(os.path.join(current_full_path, x)), x.lower())):
                item_path = os.path.join(current_full_path, item)
                relative_item_path = os.path.join(req_path, item) if req_path != '.' else item
                
                file_info = get_file_info(item_path, relative_item_path)
                items.append(file_info)
                
        except PermissionError:
            return render_template('file_manager.html', 
                                 error="Permission denied accessing directory.", 
                                 current_path=req_path, 
                                 items=[], 
                                 parent_dir=None,
                                 title="File Manager")

        # Add parent directory navigation if not in root
        parent_dir = None
        if os.path.normpath(req_path) != '.':
            parent_dir = os.path.dirname(req_path)
            if parent_dir == '':
                parent_dir = '.'

        # Log file manager access
        current_app.logger.info(
            f"File manager access: {req_path}",
            extra={
                'user_id': current_user.id,
                'path': req_path,
                'items_count': len(items)
            }
        )

        return render_template('file_manager.html', 
                             items=items, 
                             current_path=req_path, 
                             parent_dir=parent_dir,
                             title="File Manager")
                             
    except ValueError as e:
        current_app.logger.warning(f"Security violation in file manager: {e}", extra={'user_id': current_user.id})
        return render_template('file_manager.html', 
                             error="Access denied.", 
                             current_path=req_path, 
                             items=[], 
                             parent_dir=None,
                             title="File Manager")
    except Exception as e:
        current_app.logger.error(f"Error listing files for path {req_path}: {e}", extra={'user_id': current_user.id})
        return render_template('file_manager.html', 
                             error="An error occurred while listing files.", 
                             current_path=req_path, 
                             items=[], 
                             parent_dir=None,
                             title="File Manager")

@bp.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    """Create a new folder"""
    try:
        path = request.form.get('path', '.')
        folder_name = request.form.get('folder_name')

        if not folder_name:
            return jsonify(success=False, error="Folder name is required.")

        # Validate folder name
        secure_name = werkzeug.utils.secure_filename(folder_name)
        if not secure_name or secure_name != folder_name:
            return jsonify(success=False, error="Invalid folder name. Use only letters, numbers, hyphens, and underscores.")

        full_path = get_full_path(os.path.join(path, folder_name))

        if os.path.exists(full_path):
            return jsonify(success=False, error="Folder already exists.")

        os.makedirs(full_path)
        
        # Log folder creation
        current_app.logger.info(
            f"Folder created: {os.path.join(path, folder_name)}",
            extra={'user_id': current_user.id, 'action': 'create_folder'}
        )
        
        return jsonify(success=True, message="Folder created successfully.")
        
    except ValueError as e:
        current_app.logger.warning(f"Security violation in create_folder: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except PermissionError:
        return jsonify(success=False, error="Permission denied. Cannot create folder.")
    except Exception as e:
        current_app.logger.error(f"Error creating folder: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while creating the folder.")

@bp.route('/create_file', methods=['POST'])
@login_required
def create_file():
    """Create a new file"""
    try:
        path = request.form.get('path', '.')
        file_name = request.form.get('file_name')

        if not file_name:
            return jsonify(success=False, error="File name is required.")

        # Validate file name
        secure_name = werkzeug.utils.secure_filename(file_name)
        if not secure_name or secure_name != file_name:
            return jsonify(success=False, error="Invalid file name. Use only letters, numbers, hyphens, underscores, and dots.")

        full_path = get_full_path(os.path.join(path, file_name))

        if os.path.exists(full_path):
            return jsonify(success=False, error="File already exists.")

        # Create empty file
        with open(full_path, 'w') as f:
            f.write('')
            
        # Log file creation
        current_app.logger.info(
            f"File created: {os.path.join(path, file_name)}",
            extra={'user_id': current_user.id, 'action': 'create_file'}
        )
        
        return jsonify(success=True, message="File created successfully.")
        
    except ValueError as e:
        current_app.logger.warning(f"Security violation in create_file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except PermissionError:
        return jsonify(success=False, error="Permission denied. Cannot create file.")
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

        full_path = get_full_path(item_path)

        if not os.path.exists(full_path):
            return jsonify(success=False, error="Item not found.")

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
            f"Item deleted: {item_path}",
            extra={'user_id': current_user.id, 'action': action, 'is_directory': is_directory}
        )

        return jsonify(success=True, message="Item deleted successfully.")
        
    except ValueError as e:
        current_app.logger.warning(f"Security violation in delete_item: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except PermissionError:
        return jsonify(success=False, error="Permission denied. Cannot delete item.")
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

        full_path = get_full_path(file_path)

        if not os.path.exists(full_path):
            return jsonify(success=False, error="File not found.")

        if os.path.isdir(full_path):
            return jsonify(success=False, error="Cannot view directory content.")

        # Check file size (limit to 1MB for viewing)
        file_size = os.path.getsize(full_path)
        if file_size > 1024 * 1024:  # 1MB
            return jsonify(success=False, error="File is too large to view (max 1MB).")

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
            f"File viewed: {file_path}",
            extra={'user_id': current_user.id, 'action': 'view_file', 'file_size': file_size}
        )

        return jsonify(success=True, content=content, size=format_file_size(file_size))

    except ValueError as e:
        current_app.logger.warning(f"Security violation in view_file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except PermissionError:
        return jsonify(success=False, error="Permission denied. Cannot read file.")
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

        full_path = get_full_path(file_path)

        if not os.path.exists(full_path):
            abort(404, "File not found.")

        if os.path.isdir(full_path):
            abort(400, "Cannot download directory.")

        # Log file download
        current_app.logger.info(
            f"File downloaded: {file_path}",
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

    except ValueError as e:
        current_app.logger.warning(f"Security violation in download_file: {e}", extra={'user_id': current_user.id})
        abort(403, "Access denied.")
    except Exception as e:
        current_app.logger.error(f"Error downloading file {file_path}: {e}", extra={'user_id': current_user.id})
        abort(500, "An error occurred while downloading the file.")

@bp.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    """Upload a file"""
    try:
        path = request.form.get('path', '.')
        
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

            full_path = get_full_path(os.path.join(path, filename))

            # Check if file already exists
            if os.path.exists(full_path):
                return jsonify(success=False, error="File already exists.")

            # Save the file
            file.save(full_path)

            # Log file upload
            current_app.logger.info(
                f"File uploaded: {os.path.join(path, filename)}",
                extra={'user_id': current_user.id, 'action': 'upload_file', 'filename': filename}
            )

            return jsonify(success=True, message="File uploaded successfully.")

    except ValueError as e:
        current_app.logger.warning(f"Security violation in upload_file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while uploading the file.")

@bp.route('/rename_item', methods=['POST'])
@login_required
def rename_item():
    """Rename a file or folder"""
    try:
        old_path = request.form.get('old_path')
        new_name = request.form.get('new_name')

        if not old_path or not new_name:
            return jsonify(success=False, error="Both old path and new name are required.")

        # Secure the new name
        secure_new_name = werkzeug.utils.secure_filename(new_name)
        if not secure_new_name or secure_new_name != new_name:
            return jsonify(success=False, error="Invalid new name.")

        old_full_path = get_full_path(old_path)
        
        if not os.path.exists(old_full_path):
            return jsonify(success=False, error="Item not found.")

        # Create new path
        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, new_name) if parent_dir != '.' else new_name
        new_full_path = get_full_path(new_path)

        if os.path.exists(new_full_path):
            return jsonify(success=False, error="An item with that name already exists.")

        # Rename the item
        os.rename(old_full_path, new_full_path)

        # Log rename action
        current_app.logger.info(
            f"Item renamed: {old_path} -> {new_path}",
            extra={'user_id': current_user.id, 'action': 'rename_item'}
        )

        return jsonify(success=True, message="Item renamed successfully.")

    except ValueError as e:
        current_app.logger.warning(f"Security violation in rename_item: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="Access denied.")
    except PermissionError:
        return jsonify(success=False, error="Permission denied. Cannot rename item.")
    except Exception as e:
        current_app.logger.error(f"Error renaming item: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while renaming the item.")

@bp.route('/get_disk_usage')
@login_required
def get_disk_usage():
    """Get disk usage information"""
    try:
        base_dir = get_base_dir()
        
        total_size = 0
        file_count = 0
        folder_count = 0
        
        for root, dirs, files in os.walk(base_dir):
            folder_count += len(dirs)
            file_count += len(files)
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                except (OSError, IOError):
                    continue  # Skip files we can't access

        return jsonify({
            'success': True,
            'total_size': format_file_size(total_size),
            'total_size_bytes': total_size,
            'file_count': file_count,
            'folder_count': folder_count
        })

    except Exception as e:
        current_app.logger.error(f"Error getting disk usage: {e}", extra={'user_id': current_user.id})
        return jsonify(success=False, error="An error occurred while calculating disk usage.")