from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from langchain.chat_models import ChatOpenAI
from prompt import SUGGESTOR_SYSTEM_PROMPT, CLASSIFIER_SYSTEM_PROMPT, CONCLUSION_SYSTEM_PROMPT, REMINDER_SYSTEM_PROMPT
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain.schema import HumanMessage, AIMessage

# LLMs
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
suggestion_llm = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY)
decider_llm = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY)

# Define state
class State(TypedDict):
    messages: Annotated[list, add_messages]
    checklist: list
    current_task_index: int
    classifier_output: str

# Nodes
def classify_user_response(state: State) -> State:
    response = [{"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT}] + state["messages"]
    response += [{"role": "user", "content": "Classify the user's most recent message with one of the valid labels. Only respond with the exact label. No explanations."}]
    result = decider_llm.invoke(response).content.strip().lower()
    if result.split("_")[0] not in ["yes","no","update","start","skip"]:
        print("raise alarm", result)
        state["classifier_output"] = "no"
    else:
        state["classifier_output"] = result
    print("classifier state done")
    return state

def handle_start(state: State) -> State:
    task = state["checklist"][0]["task"]
    cur_msg = [{"role": "system", "content": f"Provide an introduction message to get started as a task-tracker/planner agent. Start by asking about {task}"}] + state["messages"]
    bot_msg = suggestion_llm.invoke(cur_msg).content
    state["messages"].append(AIMessage(content=bot_msg))
    print("start state done")
    return state

def handle_yes_or_skip(state: State) -> State:
    print("yes or skip done")
    output = state["classifier_output"]
    if output == "yes":
        state["checklist"][state["current_task_index"]]["status"] = "done"
    else:
        state["checklist"][state["current_task_index"]]["status"] = "pending"

    # Move to next incomplete task
    state["current_task_index"] += 1
    while state["current_task_index"] < len(state["checklist"]) and state["checklist"][state["current_task_index"]]["status"] == "done":
        state["current_task_index"] += 1

    if state["current_task_index"] >= len(state["checklist"]):
        # check for pending ones
        for i, item in enumerate(state["checklist"]):
            if item["status"] != "done":
                state["current_task_index"] = i
                task = item["task"]
                cur_msg = [{"role": "system", "content": REMINDER_SYSTEM_PROMPT}] + state["messages"]
                cur_msg += [{"role": "user", "content": f"{task} is still pending. Provide an update on it"}]
                bot_msg = suggestion_llm.invoke(cur_msg).content
                state["messages"].append(AIMessage(content=bot_msg))
                return state
        # all tasks done
        else:
            state["classifier_output"] = "end"
            cur_msg = [{"role": "system", "content": CONCLUSION_SYSTEM_PROMPT}] + state["messages"]
            cur_msg += [{"role":"user","content":"Provide a concluding message summarizing all decisions taken based on chat history. No follow up questions to be asked"}]
            bot_msg = suggestion_llm.invoke(cur_msg).content
            state["messages"].append(AIMessage(content=bot_msg))
            return state
    else:
        #state["current_task_index"] = index
        next_task = state["checklist"][state["current_task_index"]]["task"]
        cur_msg = [{"role":"system","content":f"Ask the user if we can move to the next task {next_task}. Make use of chat history"}] + state["messages"]
        bot_msg = suggestion_llm.invoke(cur_msg).content
        bot_msg = f"Great! Next task: '{next_task}'. Have you completed this?"
        state["messages"].append(AIMessage(content=bot_msg))
        return state

def handle_update(state: State) -> State:
    print("update done")
    task = state["classifier_output"].split("_")[1].lower()
    idx = next(i for i, d in enumerate(state["checklist"]) if d["task"].lower() == task)
    state["current_task_index"] = idx
    state["checklist"][idx]["status"] = "pending"
    cur_msg = [{"role": "system", "content": REMINDER_SYSTEM_PROMPT}] + state["messages"]
    cur_msg += [{"role": "user", "content": f"{task} is still pending. Provide an update on it"}]
    bot_msg = suggestion_llm.invoke(cur_msg).content
    state["messages"].append(AIMessage(content=bot_msg))
    return state

def handle_no_or_unknown(state: State) -> State:
    print("suggest done")
    cur_msg = [{"role": "system", "content": SUGGESTOR_SYSTEM_PROMPT}] + state["messages"]
    bot_msg = suggestion_llm.invoke(cur_msg).content
    state["messages"].append(AIMessage(content=bot_msg))
    return state

# Graph setup
graph = StateGraph(State)
graph.add_node("classify", RunnableLambda(classify_user_response))
graph.add_node("start", RunnableLambda(handle_start))
graph.add_node("yes_or_skip", RunnableLambda(handle_yes_or_skip))
graph.add_node("update", RunnableLambda(handle_update))
graph.add_node("fallback", RunnableLambda(handle_no_or_unknown))

graph.set_entry_point("classify")

graph.add_conditional_edges("classify", lambda state: state["classifier_output"].split("_")[0].lower(), {
    "start": "start",
    "yes": "yes_or_skip",
    "skip": "yes_or_skip",
    "no": "fallback",
    "update": "update"
})


'''
graph.add_conditional_edges("yes_or_skip", lambda state: state["classifier_output"], {
    "yes": "classify",
    "skip": "classify",
    "end": END
})
'''

# terminal edge
#for node in ["fallback", "update", "start"]:
#    graph.add_edge(node, "classify")

# Compile graph
app = graph.compile()
