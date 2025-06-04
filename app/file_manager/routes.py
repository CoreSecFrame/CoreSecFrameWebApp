import os
import shutil
from flask import render_template, request, jsonify, current_app
from app.file_manager import bp
import werkzeug # Add this import

# Define a base directory for file operations.
# IMPORTANT: This should be configured securely in a real application.
# For this example, we'll create a folder in the instance path.
BASE_WORKING_DIR_NAME = 'user_files'

def get_base_dir():
    base_dir = os.path.join(current_app.instance_path, BASE_WORKING_DIR_NAME)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    return base_dir

def get_full_path(path):
    base_dir = get_base_dir()
    # Securely join the path and prevent escaping the base directory.
    full_path = os.path.normpath(os.path.join(base_dir, path))
    if not full_path.startswith(base_dir):
        raise ValueError("Attempted access outside base directory.")
    return full_path

@bp.route('/')
def index():
    return list_files() # Redirect to list_files to show root content by default

@bp.route('/list')
def list_files_route():
    return list_files()

def list_files(path="."): # Added path parameter with default
    try:
        req_path = request.args.get('path', path) # Get path from request or use default
        current_full_path = get_full_path(req_path)

        if not os.path.exists(current_full_path) or not os.path.isdir(current_full_path):
            return render_template('file_manager.html', error="Path does not exist or is not a directory.", current_path=req_path)

        items = []
        for item in os.listdir(current_full_path):
            item_path = os.path.join(current_full_path, item)
            is_dir = os.path.isdir(item_path)
            items.append({'name': item, 'is_dir': is_dir, 'path': os.path.join(req_path, item)})

        # Add parent directory navigation if not in root
        parent_dir = None
        if os.path.normpath(req_path) != '.':
            parent_dir = os.path.dirname(req_path)
            if parent_dir == '': # Handle case where dirname of 'folder' is ''
                parent_dir = '.'


        return render_template('file_manager.html', items=items, current_path=req_path, parent_dir=parent_dir)
    except ValueError as e:
        return render_template('file_manager.html', error=str(e), current_path=req_path)
    except Exception as e:
        current_app.logger.error(f"Error listing files for path {req_path}: {e}")
        return render_template('file_manager.html', error="An error occurred while listing files.", current_path=req_path)


@bp.route('/create_folder', methods=['POST'])
def create_folder():
    try:
        path = request.form.get('path', '.')
        folder_name = request.form.get('folder_name')

        if not folder_name or not werkzeug.utils.secure_filename(folder_name): # Use werkzeug.utils.secure_filename
            return jsonify(success=False, error="Invalid folder name.")

        full_path = get_full_path(os.path.join(path, folder_name))

        if os.path.exists(full_path):
            return jsonify(success=False, error="Folder already exists.")

        os.makedirs(full_path)
        return jsonify(success=True, message="Folder created successfully.")
    except ValueError as e:
        return jsonify(success=False, error=str(e))
    except Exception as e:
        current_app.logger.error(f"Error creating folder: {e}")
        return jsonify(success=False, error="An error occurred while creating the folder.")

@bp.route('/create_file', methods=['POST'])
def create_file():
    try:
        path = request.form.get('path', '.')
        file_name = request.form.get('file_name')

        if not file_name or not werkzeug.utils.secure_filename(file_name): # Use werkzeug.utils.secure_filename
            return jsonify(success=False, error="Invalid file name.")

        full_path = get_full_path(os.path.join(path, file_name))

        if os.path.exists(full_path):
            return jsonify(success=False, error="File already exists.")

        with open(full_path, 'w') as f:
            f.write('') # Create an empty file
        return jsonify(success=True, message="File created successfully.")
    except ValueError as e:
        return jsonify(success=False, error=str(e))
    except Exception as e:
        current_app.logger.error(f"Error creating file: {e}")
        return jsonify(success=False, error="An error occurred while creating the file.")

@bp.route('/delete_item', methods=['POST'])
def delete_item():
    try:
        item_path = request.form.get('item_path') # This is relative to BASE_DIR
        if not item_path:
            return jsonify(success=False, error="Item path is required.")

        full_path = get_full_path(item_path)

        if not os.path.exists(full_path):
            return jsonify(success=False, error="Item not found.")

        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)

        return jsonify(success=True, message="Item deleted successfully.")
    except ValueError as e:
        return jsonify(success=False, error=str(e))
    except Exception as e:
        current_app.logger.error(f"Error deleting item {item_path}: {e}")
        return jsonify(success=False, error="An error occurred while deleting the item.")
