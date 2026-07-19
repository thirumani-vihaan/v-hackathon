import os
import paho.mqtt.publish as mqtt_publish
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

@tool
def issue_mqtt_command(zone: str, reason: str, score: float) -> str:
    """Issues a shutdown command to the industrial zone actuator over MQTT."""
    try:
        mqtt_publish.single(
            "vhackathon/actuator/shutdown", 
            payload=f'{{"zone": "{zone}", "reason": "{reason}", "score": {score}}}',
            hostname="test.mosquitto.org"
        )
        return "SHUTDOWN_COMMAND_ISSUED"
    except Exception as e:
        return f"SHUTDOWN_FAILED: {e}"

class ActionAgent:
    """True Agentic Reasoning node: evaluates physics output and autonomously decides to act."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.tools = [issue_mqtt_command]
        if self.api_key:
            self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=self.api_key, temperature=0.0)
            template = '''Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''
            self.prompt = PromptTemplate.from_template(template)
            self.agent = create_react_agent(self.llm, self.tools, self.prompt)
            self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=False, handle_parsing_errors=True)
        else:
            self.agent_executor = None

    def decide_and_act(self, zone: str, risk_score: float, forecast_minutes: float) -> str:
        # Offline / Test fallback
        if not self.agent_executor:
            if risk_score >= 80 or (forecast_minutes is not None and forecast_minutes <= 5.0):
                return issue_mqtt_command.invoke({"zone": zone, "reason": "CRITICAL_RISK", "score": risk_score})
            return "NONE"

        query = (
            f"The current zone is {zone}. The compound risk score is {risk_score} out of 100. "
            f"The forecasted time until a critical IDLH (lethal) gas limit is reached is {forecast_minutes} minutes. "
            f"If the risk score is >= 80 OR the forecast is <= 5.0 minutes, you MUST use the issue_mqtt_command tool to shut down the plant. "
            f"Otherwise, do not issue the command. What did you decide?"
        )
        
        try:
            res = self.agent_executor.invoke({"input": query})
            ans = res["output"].upper()
            if "SHUTDOWN" in ans or "ISSUED" in ans:
                return "SHUTDOWN_COMMAND_ISSUED"
            return "NONE"
        except Exception as e:
            if risk_score >= 80 or (forecast_minutes is not None and forecast_minutes <= 5.0):
                return issue_mqtt_command.invoke({"zone": zone, "reason": "CRITICAL_RISK_FALLBACK", "score": risk_score})
            return f"ERROR: {e}"
