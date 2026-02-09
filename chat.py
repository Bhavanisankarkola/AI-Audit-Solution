import json
from typing import List
from crewai import Agent, LLM
from crewai.flow import Flow, listen, or_,  router, start
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from crew import Audit

load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv("MODEL_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.getenv("MODEL_SECRET_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_REGION")
MODEL_NAME = os.getenv("MODEL_NAME")

# Ensure LLM is available for flow agents
llm = LLM(model = MODEL_NAME, 
          aws_access_key_id=AWS_ACCESS_KEY_ID,
          aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
          aws_region_name=AWS_DEFAULT_REGION) 

class ChatState(BaseModel):
    current_message: str = ""
    conversation_history: List[dict] = []
    current_agent: str = ""
    current_agent_response: str = ""
    current_agent_references: str = ""
    classification: str = ""


class ChatFlow(Flow[ChatState]):
    def __init__(self):
        super().__init__()  

    @start()
    def initial_processing(self):
        # Extract the current message from inputs
        if hasattr(self.state, 'current_message') and not self.state.current_message:
            self.state.current_message = self.inputs.get('current_message', '')
    
    @router(initial_processing)
    def classify_message(self):
        if not self.state.current_message:
            self.state.current_message = self.inputs.get('current_message', '')
    
        # Create agent using config
        classification_agent = Agent(
            role="User Prompt Classification Agent",
            goal="Classify the user prompt into one of the following categories: pleasantries, question, or unrelated.",
            backstory="You are a user prompt classification agent."
                "You understand if the user is just sending a pleasantry or a general conversation item - then return 'pleasantries'."
                "If the user is asking a question related to audit reports, financial data, or internal compliance - then return 'question'."
                "If the user is asking a question that is clearly unrelated to the audit context - then return 'unrelated'.",
            verbose=True,
            llm=llm,
            allow_delegation=False
        )

        prompt = """Evaluate the user prompt: '{0}'
                Return the classification result as a single word: pleasantries,
                question, or unrelated.""".format(self.state.current_message)

        result = classification_agent.kickoff(prompt).raw

        self.state.classification = result.strip().lower()

        if "pleasantries" in self.state.classification:
            return "respond_to_pleasantries"
        elif "question" in self.state.classification:
            return "respond_to_question"
        else:
            return "respond_to_unrelated"

    @listen("respond_to_pleasantries")
    def answer_pleasantries(self):
        simple_response_agent = Agent(
            role="Audit Assistant",
            goal="Respond to the user's pleasantry",
            backstory="You are a professional yet friendly Audit Assistant."
                       "You respond to the user's pleasantry with a professional, short message.",
            verbose=True,
            llm=llm,
            allow_delegation=False
        )

        self.state.current_agent_response = simple_response_agent.kickoff(
            f"Respond to the user's pleasantry: '{self.state.current_message}'."
        ).raw
        self.state.current_agent_references = ""  # No references for pleasantries
        self.state.current_agent = "simple_response_agent"

    @listen("respond_to_question")
    def answer_question(self):
        try:
            inputs = {
                "query": self.state.current_message,
            }
            
            # Use the Audit Crew defined in crew.py
            audit_crew = Audit()
            crew_output = audit_crew.crew().kickoff(inputs=inputs)
            
            # Parse the crew output - it returns a CrewOutput object
            output_dict = self._parse_crew_output(crew_output)
            
            self.state.current_agent_response = output_dict.get("answer", str(crew_output))
            self.state.current_agent_references = output_dict.get("references", "")
            self.state.current_agent = "audit_crew"
        except Exception as e:
            self.state.current_agent_response = f"Error processing question: {str(e)}"
            self.state.current_agent_references = ""
            self.state.current_agent = "audit_crew"

    @listen("respond_to_unrelated")
    def answer_unrelated(self):
        self.state.current_agent_response = "I am an Audit Reporting Assistant. Please ask questions related to audit reports or compliance."
        self.state.current_agent_references = ""  # No references for unrelated
        self.state.current_agent = "unrelated_agent"

    def _parse_crew_output(self, crew_output):
        """
        Parse CrewOutput object and extract answer and references
        """
        try:
            # Try to get the raw output
            if hasattr(crew_output, 'raw'):
                output_str = crew_output.raw
            else:
                output_str = str(crew_output)
            
            # Try to parse as JSON
            try:
                parsed = json.loads(output_str)
                return {
                    "answer": parsed.get("answer", output_str),
                    "references": parsed.get("references", "")
                }
            except json.JSONDecodeError:
                # If not JSON, return as is
                return {
                    "answer": output_str,
                    "references": ""
                }
        except Exception as e:
            return {
                "answer": str(crew_output),
                "references": ""
            }

    @listen(or_(answer_pleasantries, answer_question, answer_unrelated))
    def send_response(self):
        # Update the conversation history
        self.state.conversation_history.append(
            {"role": "user", "content": self.state.current_message}
        )
        self.state.conversation_history.append(
            {"role": "assistant", "content": self.state.current_agent_response,
             "references": self.state.current_agent_references}
        )

        # Return a structured response
        return {
            "answer": self.state.current_agent_response,
            "references": self.state.current_agent_references
        }