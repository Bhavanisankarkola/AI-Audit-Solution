import os
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from utils import (
    create_session, get_all_sessions, get_session_messages, save_message, delete_session,
    retrieve_and_answer, allowed_file, save_uploaded_file, process_document
)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size


# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('home.html')


@app.route('/chat')
def chat():
    """Chat interface"""
    # Create session only if it doesn't exist
    if 'session_id' not in session:
        session['session_id'] = create_session()

    # Get chat history
    sessions = get_all_sessions()
    messages = get_session_messages(session['session_id'])

    return render_template('chat.html', sessions=sessions, messages=messages, current_session=session['session_id'])


@app.route('/upload')
def upload():
    """Upload interface"""
    return render_template('upload.html')


@app.route('/api/upload_documents', methods=['POST'])
def upload_documents():
    """Handle document upload"""
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist('files')
    uploaded_files = []

    for file in files:
        filename, filepath = save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
        if filename:
            uploaded_files.append(filename)
            process_document(filepath, filename)

    return jsonify({
        "success": True,
        "message": f"Uploaded {len(uploaded_files)} file(s)",
        "files": uploaded_files
    }), 200



@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Handle message sending"""
    data = request.json
    user_message = data.get('message')
    session_id = session.get('session_id')

    if not user_message or not session_id:
        return jsonify({"error": "Invalid request"}), 400

    # Save user message
    save_message(session_id, 'user', user_message)

    # Get AI response
    response = retrieve_and_answer(user_message)
    full_response = f"{response['answer']}\n\n{response['references']}"

    # Save assistant message
    save_message(session_id, 'assistant', full_response)

    return jsonify({
        "answer": response['answer'],
        "references": response['references']
    })


@app.route('/api/new_chat', methods=['POST'])
def new_chat():
    """Create a new chat session"""
    new_session_id = create_session()
    session['session_id'] = new_session_id
    return jsonify({"session_id": new_session_id})


@app.route('/api/load_session/<session_id>', methods=['GET'])
def load_session(session_id):
    """Load a specific chat session"""
    session['session_id'] = session_id
    messages = get_session_messages(session_id)
    return jsonify({"messages": [dict(msg) for msg in messages]})


@app.route('/api/delete_session/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    """Delete a chat session"""
    delete_session(session_id)

    # If deleted current session, create new one
    if session.get('session_id') == session_id:
        session['session_id'] = create_session()

    return jsonify({"success": True})


if __name__ == '__main__':
    app.run()