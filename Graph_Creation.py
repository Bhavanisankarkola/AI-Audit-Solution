import re
from typing import List, Dict, Tuple
from neo4j import GraphDatabase
import PyPDF2
from dataclasses import dataclass

@dataclass
class PolicySection:
    """Data class to represent a policy section"""
    policy_name: str
    section_number: str
    section_heading: str
    content: str
    parent_policy: str

class PolicyDocumentParser:
    """Parser to extract policy sections from documents"""
    
    def __init__(self):
        self.section_pattern = re.compile(r'^(\d+)\.\s+(.+?)$', re.MULTILINE)
        self.policy_pattern = re.compile(r'Policy\s+(\d+):\s+(.+?)(?=\n)', re.IGNORECASE)
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file"""
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    
    def identify_policies(self, text: str) -> List[Dict]:
        """Identify all policies in the document"""
        policies = []
        matches = self.policy_pattern.finditer(text)
        
        for match in matches:
            policy_num = match.group(1)
            policy_name = match.group(2).strip()
            policies.append({
                'number': policy_num,
                'name': policy_name,
                'start_pos': match.start()
            })
        
        return policies
    
    def parse_policy_sections(self, text: str) -> List[PolicySection]:
        """Parse all sections from the policy document"""
        policies = self.identify_policies(text)
        all_sections = []
        
        for i, policy in enumerate(policies):
            start_pos = policy['start_pos']
            end_pos = policies[i + 1]['start_pos'] if i + 1 < len(policies) else len(text)
            
            policy_text = text[start_pos:end_pos]
            sections = self._extract_sections_from_policy(
                policy_text, 
                policy['name'], 
                policy['number']
            )
            all_sections.extend(sections)
        
        return all_sections
    
    def _extract_sections_from_policy(self, policy_text: str, 
                                     policy_name: str, 
                                     policy_num: str) -> List[PolicySection]:
        """Extract individual sections from a policy"""
        sections = []
        section_matches = list(self.section_pattern.finditer(policy_text))
        
        for i, match in enumerate(section_matches):
            section_num = match.group(1)
            section_heading = match.group(2).strip()
            
            start_pos = match.end()
            end_pos = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(policy_text)
            
            content = policy_text[start_pos:end_pos].strip()
            
            section = PolicySection(
                policy_name=policy_name,
                section_number=section_num,
                section_heading=section_heading,
                content=content,
                parent_policy=f"Policy {policy_num}"
            )
            sections.append(section)
        
        return sections

class Neo4jPolicyGraph:
    """Neo4j graph database handler for policy documents"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close database connection"""
        self.driver.close()
    
    def create_policy_graph(self, sections: List[PolicySection]):
        """Create policy graph with sections and relationships"""
        with self.driver.session() as session:
            # Create policies first
            policies = set(section.parent_policy for section in sections)
            for policy in policies:
                session.execute_write(self._create_policy_node, policy)
            
            # Create sections and relationships
            for section in sections:
                session.execute_write(self._create_section_with_relationship, section)
    
    @staticmethod
    def _create_policy_node(tx, policy_name: str):
        """Create a policy node in Neo4j"""
        query = """
        MERGE (p:Policy {name: $policy_name})
        SET p.created_at = datetime()
        RETURN p
        """
        tx.run(query, policy_name=policy_name)
    
    @staticmethod
    def _create_section_with_relationship(tx, section: PolicySection):
        """Create section node and establish relationship with policy"""
        query = """
        MATCH (p:Policy {name: $parent_policy})
        MERGE (s:Section {
            section_number: $section_number,
            heading: $section_heading,
            parent_policy: $parent_policy
        })
        SET s.content = $content,
            s.policy_name = $policy_name,
            s.created_at = datetime()
        MERGE (p)-[r:HAS_SECTION]->(s)
        SET r.order = toInteger($section_number)
        RETURN s, r
        """
        tx.run(
            query,
            parent_policy=section.parent_policy,
            section_number=section.section_number,
            section_heading=section.section_heading,
            content=section.content,
            policy_name=section.policy_name
        )
    
    def query_policy_structure(self, policy_name: str) -> List[Dict]:
        """Query all sections for a specific policy"""
        with self.driver.session() as session:
            result = session.execute_read(self._get_policy_sections, policy_name)
            return result
    
    @staticmethod
    def _get_policy_sections(tx, policy_name: str):
        """Retrieve all sections for a policy"""
        query = """
        MATCH (p:Policy {name: $policy_name})-[r:HAS_SECTION]->(s:Section)
        RETURN s.section_number as number, 
               s.heading as heading, 
               s.content as content
        ORDER BY toInteger(s.section_number)
        """
        result = tx.run(query, policy_name=policy_name)
        return [dict(record) for record in result]

# Main execution function
def process_policy_document(pdf_path: str, neo4j_uri: str, 
                           neo4j_user: str, neo4j_password: str):
    """Main function to process policy document and create Neo4j graph"""
    
    # Initialize parser
    parser = PolicyDocumentParser()
    
    # Extract and parse document
    print("Extracting text from PDF...")
    text = parser.extract_text_from_pdf(pdf_path)
    
    print("Parsing policy sections...")
    sections = parser.parse_policy_sections(text)
    
    print(f"Found {len(sections)} sections across all policies")
    
    # Create Neo4j graph
    print("Creating Neo4j graph...")
    graph = Neo4jPolicyGraph(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        graph.create_policy_graph(sections)
        print("Graph created successfully!")
        
        # Example query
        print("\nQuerying Policy 1 structure...")
        result = graph.query_policy_structure("Policy 1")
        for section in result:
            print(f"  Section {section['number']}: {section['heading']}")
    
    finally:
        graph.close()

# Usage example
if __name__ == "__main__":
    process_policy_document(
        pdf_path=r"C:\Users\kolab\OneDrive\Documents\AI Audit Solution\Data\IT Policy Manual.pdf",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="Kola1234"
    )

