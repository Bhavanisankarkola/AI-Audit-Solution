import os
import json
import uuid
from datetime import datetime
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_aws import ChatBedrock
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
import urllib.parse
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Configuration
DB_URL = os.getenv('DB_URL', 'postgresql://postgres:admin123@localhost:5432/postgres')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
MODEL_ID = os.getenv('AWS_MODEL')
AWS_REGION_NAME = os.getenv('AWS_REGION_NAME')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

# Initialize AI models
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY,
    task_type="RETRIEVAL_DOCUMENT"
)

aws_model = ChatBedrock(
    model_id=MODEL_ID,
    aws_access_key_id= ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name = AWS_REGION_NAME 
)
gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=GOOGLE_API_KEY)
output_parser = StrOutputParser()

# Prompt template
prompt_template = """
Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
Context:\n {context}?\n
Question: \n{question}\n

Answer:
"""
prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
chain = prompt | aws_model | output_parser


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
            # Messages will be deleted automatically due to CASCADE
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        conn.commit()

def retrieve_and_answer(query):
    """Retrieve relevant chunks and generate answer"""
    # Embed the query
    query_embedding = embeddings.embed_query(query, output_dimensionality=1536)

    # Retrieve from database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM match_chunks(%s::vector, %s)
            """, (query_embedding, 5))
            results = cur.fetchall()

    # Combine context
    context = "".join(row[2] for row in results)

    # Generate answer
    answer = chain.invoke({"context": context, "question": query})

    # Build references only if answer indicates information was found
    references = ""
    answer_lower = answer.lower()
    
    # Check for various phrases indicating "not available"
    not_available_phrases = [
        "not available in the context"
    ]
    
    has_no_answer = any(phrase in answer_lower for phrase in not_available_phrases)
    
    if not has_no_answer and results:
        references_map = {}
        for row in results:
            file_path = row[-1]
            doc_title = row[-2]
            if file_path not in references_map:
                references_map[file_path] = {"title": doc_title}

        links = []
        for path, info in references_map.items():
            safe_path = path.replace("\\", "/")
            url_path = urllib.parse.quote(safe_path)
            links.append(f"[{info['title']}]({url_path})")

        references = "References: " + ", ".join(links) if links else ""

    return {
        "answer": answer,
        "references": references
    }

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, upload_folder):
    """Save an uploaded file to the upload folder"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid overwrites
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return filename, filepath
    return None, None


def process_document(filepath, filename):
    pass
