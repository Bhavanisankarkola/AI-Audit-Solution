from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
import os
from agents.tools import doc_search
from pydantic import BaseModel

load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv("MODEL_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.getenv("MODEL_SECRET_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_REGION")
MODEL_NAME = os.getenv("MODEL_NAME")
llm = LLM(model = MODEL_NAME, 
		  aws_access_key_id=AWS_ACCESS_KEY_ID,
          aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
          aws_region_name=AWS_DEFAULT_REGION)

vector_db = doc_search.VectorSearch()
websearch = doc_search.WebSearch()

class Audit_Result(BaseModel):
	answer: str
	references: str

@CrewBase
class Audit():
	agents_config = 'agents/config/agents.yaml'
	tasks_config = 'agents/config/tasks.yaml'

	@agent
	def audit_agent(self) -> Agent:
		return Agent(
			config=self.agents_config['audit_agent'],
			verbose=True,
			llm=llm,
			allow_delegation=False,
			tools = [vector_db.retrieve_and_answer,websearch.search_query]
		)

	@task
	def audit_task(self) -> Task:
		return Task(
			config=self.tasks_config['audit_task'],
			output_json=Audit_Result
		)

	@crew
	def crew(self) -> Crew:
		return Crew(
			agents=self.agents, 
			tasks=self.tasks, 
			process=Process.sequential,
			verbose=True
		)