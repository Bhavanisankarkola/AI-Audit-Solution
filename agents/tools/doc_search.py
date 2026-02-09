from crewai.tools import tool
from ddgs import DDGS
import os
from dotenv import load_dotenv
import psycopg
import urllib.parse
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
load_dotenv()

# Configuration
DB_URL = os.getenv('DB_URL', 'postgresql://postgres:admin123@localhost:5432/postgres')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY,
    task_type="RETRIEVAL_DOCUMENT"
)

class VectorSearch:
    def get_db_connection(self):
        """Get a database connection"""
        return psycopg.connect(DB_URL)

    @tool("Vector Search Tool")
    def retrieve_and_answer(query: str):
        """
        Useful for searching authentic audit reports and internal documents. 
        Always use this tool FIRST before trying web search.
        Returns the answer derived from the documents and the references.
        """
        # Embed the query
        query_embedding = embeddings.embed_query(query, output_dimensionality=1536)

        # Retrieve from database
        try:
            with psycopg.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM match_chunks(%s::vector, %s)
                    """, (query_embedding, 5))
                    results = cur.fetchall()
        except Exception as e:
            return f"Error connecting to database: {str(e)}"
        finally:
            conn.close()

        # Combine context
        context = "".join(row[2] for row in results)

        if not context:
            return "No relevant information found in the internal documents."

        references = ""        
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
            "context": context,
            "references": references
        }
    
class WebSearch:
    @tool("Web Search Tool")
    def search_query(
        query: str
    ) -> list[dict[str, str]]:
        """DuckDuckGo text metasearch.
        Params:
        - query: text search query.
        - region: us-en, uk-en, ru-ru, etc. Defaults to us-en.
        - safesearch: on, moderate, off. Defaults to "moderate".
        - timelimit: d, w, m, y. Defaults to None.
        - max_results: maximum number of results. Defaults to 10.
        - page: page of results. Defaults to 1.
        - backend: A single or comma-delimited backends. Defaults to "auto".

        Returns:
            List of dictionaries with search results.
        """
        results = DDGS().text(query=query, region="us-en", safesearch="moderate", max_results=10)
        return results