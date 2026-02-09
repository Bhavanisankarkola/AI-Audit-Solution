import os
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from utils import (
    create_session, get_all_sessions, get_session_messages, save_message, delete_session,
    allowed_file, save_uploaded_file, process_document
)
from chat import ChatFlow
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
    
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "No files selected"}), 400

    uploaded_files = []
    failed_files = []
    processed_files = []

    for file in files:
        # Check file extension using allowed_file function
        if not allowed_file(file.filename):
            failed_files.append({
                "filename": file.filename,
                "reason": "File type not allowed. Allowed types: pdf, doc, docx, txt"
            })
            continue

        # Save the file
        filename, filepath = save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
        if filename:
            uploaded_files.append(filename)
            
            # Process the document
            try:
                process_document(filepath, filename)
                processed_files.append(filename)
            except Exception as e:
                failed_files.append({
                    "filename": filename,
                    "reason": f"Processing error: {str(e)}"
                })
                print(f"Error processing {filename}: {str(e)}")

    return jsonify({
        "success": len(processed_files) > 0,
        "message": f"Processed {len(processed_files)} file(s) successfully",
        "processed_files": processed_files,
        "failed_files": failed_files,
        "total_files": len(files)
    }), 200 if processed_files else 400



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
    try:       
        inputs = {
            'current_message': user_message,
            'id': session_id  # Pass session ID for tracking
        }
        
        chat_flow = ChatFlow()
        agent_result = chat_flow.kickoff(inputs=inputs)
        
        if isinstance(agent_result, dict):
            full_response = agent_result.get("answer", str(agent_result))
            references = agent_result.get("references", "")
        else:
            full_response = str(agent_result)
            references = ""
        
    except Exception as e:
        full_response = f"Error processing request: {str(e)}"
        references = ""

    # Save assistant message
    save_message(session_id, 'assistant', full_response)

    return jsonify({
        "answer": full_response,
        "references": references
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
    app.run(debug=True, host='0.0.0.0', port=5000)