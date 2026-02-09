import os
import json
import uuid
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
import urllib.parse
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Configuration
DB_URL = os.getenv('DB_URL', 'postgresql://postgres:admin123@localhost:5432/postgres')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

# Initialize embeddings and text splitter
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY,
    task_type="RETRIEVAL_DOCUMENT"
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=5000,
    chunk_overlap=300,
    separators=['\n\n', '\n', ' ', '']
)


# ==================== Database Operations ====================

def get_db_connection():
    """Get a database connection"""
    return psycopg.connect(DB_URL)


def create_session():
    """Create a new chat session"""
    session_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (id, user_id, metadata)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (session_id, 'default_user', json.dumps({})))
        conn.commit()
    return session_id


def get_all_sessions():
    """Retrieve all chat sessions"""
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT id, created_at, 
                       (SELECT content FROM messages WHERE session_id = sessions.id AND role = 'user' 
                        ORDER BY created_at ASC LIMIT 1) as first_message
                FROM sessions
                ORDER BY created_at DESC
                LIMIT 20
            """)
            return cur.fetchall()


def get_session_messages(session_id):
    """Get all messages for a session"""
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT role, content, created_at
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session_id,))
            return cur.fetchall()


def save_message(session_id, role, content):
    """Save a message to database"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (session_id, role, content)
                VALUES (%s, %s, %s)
            """, (session_id, role, content))
        conn.commit()


def delete_session(session_id):
    """Delete a chat session and all its messages"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        conn.commit()


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, upload_folder):
    """Save an uploaded file to the upload folder"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return filename, filepath
    return None, None


def process_document(filepath, filename):
    """Process PDF document: extract text, create chunks, generate embeddings, and store in database"""
    print(f"Processing file: {filepath}")
    
    # Read PDF and extract text
    text = ""
    with open(filepath, 'rb') as f:
        pdf_reader = PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text()
    
    print(f"Length of {filename}: {len(text)}")
    
    # Clean text encoding
    text = text.encode("utf-8", "replace").decode("utf-8")
    
    # Create chunks
    chunks = text_splitter.split_text(text)
    
    # Generate embeddings
    vectors = embeddings.embed_documents(chunks, output_dimensionality=1536)
    
    # Insert document
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO documents (title, source, content, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (filename, filepath, text, json.dumps({"status": "processed"})))
            conn.commit()
            
            # Get document ID
            cur.execute("SELECT id FROM documents WHERE source = %s", (filepath,))
            doc_id = cur.fetchone()[0]
            
            # Prepare chunk data
            data_to_insert = []
            for i, chunk in enumerate(chunks):
                data_to_insert.append(
                    (doc_id, chunk, vectors[i], i, len(chunk.split()))
                )
            
            # Insert chunks
            cur.executemany("""
                INSERT INTO chunks (document_id, content, embedding, chunk_index, token_count)
                VALUES (%s, %s, %s, %s, %s)
            """, data_to_insert)
            conn.commit()
    
    print(f"{filename} processed successfully.")
