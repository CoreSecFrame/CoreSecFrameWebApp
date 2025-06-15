import unittest
from app import create_app, db
from app.auth.models import User # Assuming User model is in app.auth.models
from app.notes.models import Note
from flask_login import login_user, logout_user

class NoteTestCase(unittest.TestCase):
    def setUp(self):
        # Try to use a specific testing configuration if available, otherwise fall back
        try:
            self.app = create_app(config_name='testing')
        except TypeError: # If create_app doesn't take config_name
             self.app = create_app() # Or however your app is created for testing

        self.app_context = self.app.app_context()
        self.app_context.push()

        # Configure Flask app for testing
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for easier testing of forms
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory SQLite

        db.create_all()
        self.client = self.app.test_client()

        # Create a test user
        self.user1 = User(username='testuser1', email='test1@example.com')
        self.user1.set_password('password123')
        db.session.add(self.user1)

        self.user2 = User(username='testuser2', email='test2@example.com')
        self.user2.set_password('password456')
        db.session.add(self.user2)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        # Assuming your login route is /auth/login and uses email
        # The actual login implementation might vary based on your User model and login route
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            # Manually log in the user for testing if direct POST is tricky
            with self.client.session_transaction() as sess:
                # This simulates Flask-Login's login_user behavior for tests
                sess['_user_id'] = user.id
                sess['_fresh'] = True
            return True # Indicates successful login for test logic

        # Fallback to actual POST request if manual session manipulation isn't enough
        # This might be needed if your login view does more than just Flask-Login's login_user
        response = self.client.post('/auth/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)
        return response.status_code == 200 and b'Logout' in response.data # Check for successful login indicator

    def logout(self):
        # Manually clear session if direct GET is tricky
        with self.client.session_transaction() as sess:
            sess.clear()
        # Also attempt the actual logout route
        return self.client.get('/auth/logout', follow_redirects=True)


    # --- Model Tests ---
    def test_create_note_model(self):
        note = Note(title='Test Note', content='This is a test note.', user_id=self.user1.id)
        db.session.add(note)
        db.session.commit()
        self.assertIsNotNone(note.id)
        self.assertEqual(note.title, 'Test Note')
        self.assertEqual(note.user_id, self.user1.id)

    # --- Route Tests (Basic Examples) ---
    def test_notes_index_unauthenticated(self):
        response = self.client.get('/notes/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Login' in response.data or b'Sign In' in response.data)

    def test_notes_index_authenticated(self):
        self.assertTrue(self.login(self.user1.email, 'password123'))
        response = self.client.get('/notes/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'My Notes' in response.data)
        self.logout()

    def test_create_new_note(self):
        self.assertTrue(self.login(self.user1.email, 'password123'))
        response = self.client.post('/notes/new', data=dict(
            title='My New Note',
            content='Content of my new note.'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Note created successfully!' in response.data)
        self.assertTrue(b'My New Note' in response.data)

        note = Note.query.filter_by(title='My New Note').first()
        self.assertIsNotNone(note)
        self.assertEqual(note.user_id, self.user1.id)
        self.logout()

    def test_view_own_note(self):
        self.assertTrue(self.login(self.user1.email, 'password123'))
        note = Note(title='Viewable Note', content='This is a viewable note.', user_id=self.user1.id)
        db.session.add(note)
        db.session.commit()

        response = self.client.get(f'/notes/{note.id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Viewable Note' in response.data)
        self.assertTrue(b'This is a viewable note.' in response.data)
        self.logout()

    def test_edit_own_note(self):
        self.assertTrue(self.login(self.user1.email, 'password123'))
        note = Note(title='Editable Note', content='Original content.', user_id=self.user1.id)
        db.session.add(note)
        db.session.commit()

        response = self.client.post(f'/notes/edit/{note.id}', data=dict(
            title='Updated Editable Note',
            content='Updated content.'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Note updated successfully!' in response.data)

        updated_note = db.session.get(Note, note.id) # Use db.session.get for SQLAlchemy 2.0+
        self.assertEqual(updated_note.title, 'Updated Editable Note')
        self.assertEqual(updated_note.content, 'Updated content.')
        self.logout()

    def test_delete_own_note(self):
        self.assertTrue(self.login(self.user1.email, 'password123'))
        note = Note(title='Deletable Note', content='This note will be deleted.', user_id=self.user1.id)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

        response = self.client.post(f'/notes/delete/{note_id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Note deleted successfully!' in response.data)

        deleted_note = db.session.get(Note, note_id) # Use db.session.get
        self.assertIsNone(deleted_note)
        self.logout()

    def test_cannot_view_others_note(self):
        note_user1 = Note(title='User1s Note', content='Secret content', user_id=self.user1.id)
        db.session.add(note_user1)
        db.session.commit()

        self.assertTrue(self.login(self.user2.email, 'password456'))
        response = self.client.get(f'/notes/{note_user1.id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'You are not authorized to view this note.' in response.data)
        self.assertFalse(b'Secret content' in response.data)
        self.logout()

    def test_cannot_edit_others_note(self):
        note_user1 = Note(title='User1s Note Edit Test', content='Original', user_id=self.user1.id)
        db.session.add(note_user1)
        db.session.commit()

        self.assertTrue(self.login(self.user2.email, 'password456'))
        response = self.client.post(f'/notes/edit/{note_user1.id}', data=dict(
            title='Attempted Edit by User2',
            content='Malicious content'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'You are not authorized to edit this note.' in response.data)

        original_note = db.session.get(Note, note_user1.id) # Use db.session.get
        self.assertEqual(original_note.title, 'User1s Note Edit Test')
        self.logout()

    def test_cannot_delete_others_note(self):
        note_user1 = Note(title='User1s Note Delete Test', content='To be kept', user_id=self.user1.id)
        db.session.add(note_user1)
        db.session.commit()
        note_id = note_user1.id

        self.assertTrue(self.login(self.user2.email, 'password456'))
        response = self.client.post(f'/notes/delete/{note_id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'You are not authorized to delete this note.' in response.data)

        self.assertIsNotNone(db.session.get(Note, note_id)) # Use db.session.get
        self.logout()

if __name__ == '__main__':
    unittest.main()
