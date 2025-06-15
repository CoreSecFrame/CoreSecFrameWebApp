from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user # Assuming Flask-Login for authentication
from app import db
from app.notes.models import Note
from app.notes.forms import NoteForm
from . import notes_bp
import markdown

# Route to display list of notes (index)
@notes_bp.route('/')
@login_required
def index():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    return render_template('notes/index.html', notes=notes)

# Route to create a new note
@notes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_note():
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(title=form.title.data, content=form.content.data, user_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        flash('Note created successfully!', 'success')
        return redirect(url_for('notes.index'))
    return render_template('notes/new_note.html', form=form, title="New Note")

# Route to view a single note
@notes_bp.route('/<int:note_id>')
@login_required
def view_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('You are not authorized to view this note.', 'danger')
        return redirect(url_for('notes.index'))
    # Render Markdown content to HTML
    note_content_html = markdown.markdown(note.content)
    return render_template('notes/view_note.html', note=note, note_content_html=note_content_html)

# Route to edit an existing note
@notes_bp.route('/edit/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('You are not authorized to edit this note.', 'danger')
        return redirect(url_for('notes.index'))
    form = NoteForm(obj=note)
    if form.validate_on_submit():
        note.title = form.title.data
        note.content = form.content.data
        db.session.commit()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('notes.view_note', note_id=note.id))
    return render_template('notes/edit_note.html', form=form, note=note, title="Edit Note")

# Route to delete a note
@notes_bp.route('/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('You are not authorized to delete this note.', 'danger')
        return redirect(url_for('notes.index'))
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully!', 'success')
    return redirect(url_for('notes.index'))
