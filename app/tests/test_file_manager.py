import os
import shutil
import unittest
from app import create_app, db # Assuming db is your SQLAlchemy instance, adjust if not used or named differently
from app.config import TestingConfig # Make sure you have a TestConfig

# BASE_DIR for test file operations, relative to the instance path of the test app
TEST_USER_FILES_DIR_NAME = 'test_user_files'

class FileManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig) # Use a specific TestConfig for your tests
        self.app_context = self.app.app_context()
        self.app_context.push()
        # If you use a database, uncomment the next line
        # db.create_all()
        self.client = self.app.test_client()

        # Define and create a test-specific base directory for file operations
        self.test_base_dir = os.path.join(self.app.instance_path, TEST_USER_FILES_DIR_NAME)
        if os.path.exists(self.test_base_dir):
            shutil.rmtree(self.test_base_dir)
        os.makedirs(self.test_base_dir)

        # Override the BASE_WORKING_DIR_NAME in file_manager routes for testing
        # This requires the file_manager blueprint to be available in self.app
        # And that its routes module can have its BASE_WORKING_DIR_NAME patched
        # This is a bit complex. A simpler way if direct patching is hard:
        # ensure your file_manager.routes.get_base_dir() can be influenced by TestConfig
        # For now, we assume the file_manager uses the 'user_files' from config,
        # and we'll ensure our test operations are within a subfolder of that or use a dedicated test folder.
        # The routes already use current_app.instance_path, so TEST_USER_FILES_DIR_NAME will be inside instance.
        # We will use this self.test_base_dir for direct file system checks in tests.
        # And for API calls, we will ensure paths are relative to TEST_USER_FILES_DIR_NAME

        # To make the test work with the existing get_base_dir() in routes.py,
        # we'll temporarily patch the BASE_WORKING_DIR_NAME in the routes module.
        from app.file_manager import routes as fm_routes
        self.original_base_dir_name = fm_routes.BASE_WORKING_DIR_NAME
        fm_routes.BASE_WORKING_DIR_NAME = TEST_USER_FILES_DIR_NAME


    def tearDown(self):
        # If you use a database, uncomment the next two lines
        # db.session.remove()
        # db.drop_all()
        self.app_context.pop()

        # Restore original base dir name after tests
        from app.file_manager import routes as fm_routes
        fm_routes.BASE_WORKING_DIR_NAME = self.original_base_dir_name

        # Clean up the test-specific base directory
        if os.path.exists(self.test_base_dir):
            shutil.rmtree(self.test_base_dir)

    def test_01_access_file_manager_index(self):
        response = self.client.get('/file_manager/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'File Manager', response.data)
        self.assertIn(b'Current Path: /', response.data) # Check if it shows root

    def test_02_create_folder(self):
        response = self.client.post('/file_manager/create_folder', data={
            'path': '.',
            'folder_name': 'test_folder'
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertTrue(json_response['success'])
        self.assertTrue(os.path.exists(os.path.join(self.test_base_dir, 'test_folder')))

    def test_03_create_file(self):
        # First create a folder to create a file in, to test path handling
        os.makedirs(os.path.join(self.test_base_dir, 'test_folder_for_file'))
        response = self.client.post('/file_manager/create_file', data={
            'path': 'test_folder_for_file',
            'file_name': 'test_file.txt'
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertTrue(json_response['success'])
        self.assertTrue(os.path.exists(os.path.join(self.test_base_dir, 'test_folder_for_file', 'test_file.txt')))

    def test_04_list_files_and_folders(self):
        # Create some items first
        os.makedirs(os.path.join(self.test_base_dir, 'folder1'))
        with open(os.path.join(self.test_base_dir, 'file1.txt'), 'w') as f:
            f.write('test')

        response = self.client.get('/file_manager/list?path=.')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'folder1', response.data)
        self.assertIn(b'file1.txt', response.data)

        # Test listing a subfolder
        response_sub = self.client.get('/file_manager/list?path=folder1')
        self.assertEqual(response_sub.status_code, 200)
        self.assertIn(b'Current Path: /folder1', response_sub.data)


    def test_05_delete_file(self):
        file_path_relative = 'file_to_delete.txt'
        file_path_abs = os.path.join(self.test_base_dir, file_path_relative)
        with open(file_path_abs, 'w') as f:
            f.write('delete me')

        self.assertTrue(os.path.exists(file_path_abs))

        response = self.client.post('/file_manager/delete_item', data={
            'item_path': file_path_relative
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertTrue(json_response['success'])
        self.assertFalse(os.path.exists(file_path_abs))

    def test_06_delete_folder(self):
        folder_path_relative = 'folder_to_delete'
        folder_path_abs = os.path.join(self.test_base_dir, folder_path_relative)
        os.makedirs(folder_path_abs)
        # Add a file inside to test recursive delete
        with open(os.path.join(folder_path_abs, 'dummy.txt'), 'w') as f:
            f.write('dummy')

        self.assertTrue(os.path.exists(folder_path_abs))

        response = self.client.post('/file_manager/delete_item', data={
            'item_path': folder_path_relative
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertTrue(json_response['success'])
        self.assertFalse(os.path.exists(folder_path_abs))

    def test_07_prevent_directory_traversal_create(self):
        response = self.client.post('/file_manager/create_folder', data={
            'path': '.',
            'folder_name': '../outside_folder'
        })
        self.assertEqual(response.status_code, 200) # Endpoint returns JSON for error
        json_response = response.get_json()
        self.assertFalse(json_response['success'])
        self.assertIn('Invalid folder name', json_response['error']) # werkzeug.secure_filename handles this
        self.assertFalse(os.path.exists(os.path.join(self.app.instance_path, 'outside_folder')))

    def test_08_prevent_directory_traversal_delete(self):
        # This test is a bit conceptual as get_full_path should prevent it.
        # We are trying to delete something outside the TEST_USER_FILES_DIR_NAME
        response = self.client.post('/file_manager/delete_item', data={
            'item_path': '../../some_other_file_hopefully_not_existing'
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertFalse(json_response['success'])
        self.assertIn('Attempted access outside base directory', json_response['error'])

    def test_09_create_folder_already_exists(self):
        os.makedirs(os.path.join(self.test_base_dir, 'existing_folder'))
        response = self.client.post('/file_manager/create_folder', data={
            'path': '.',
            'folder_name': 'existing_folder'
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertFalse(json_response['success'])
        self.assertIn('Folder already exists', json_response['error'])

    def test_10_create_file_already_exists(self):
        with open(os.path.join(self.test_base_dir, 'existing_file.txt'), 'w') as f:
            f.write('hello')
        response = self.client.post('/file_manager/create_file', data={
            'path': '.',
            'file_name': 'existing_file.txt'
        })
        self.assertEqual(response.status_code, 200)
        json_response = response.get_json()
        self.assertFalse(json_response['success'])
        self.assertIn('File already exists', json_response['error'])

if __name__ == '__main__':
    unittest.main()
