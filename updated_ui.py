import streamlit as st
from graph import app
import time
from checklist import checklist
from langchain.schema import HumanMessage, AIMessage


st.title("🧠 Task Planning Assistant")

def response_generator(response):
    for word in response.split():
        yield word + " "
        time.sleep(0.05)


# Only initialize once
if "messages" not in st.session_state:
    st.session_state.messages = []

if "checklist" not in st.session_state:
    st.session_state.checklist = checklist.copy()  # To avoid modifying original

if "current_task_index" not in st.session_state:
    st.session_state.current_task_index = 0

if "classifier_output" not in st.session_state:
    st.session_state.classifier_output = ""

# Show chat history


for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    else:
        role = "assistant"  # default fallback

    with st.chat_message(role):
        st.markdown(msg.content)

# User Input
if prompt := st.chat_input("What do you want to say?"):
    st.session_state.messages.append(HumanMessage(content=prompt))

    with st.chat_message("user"):
        st.markdown(prompt)

    # Create state object
    state = {
        "messages": st.session_state.messages,
        "checklist": st.session_state.checklist,
        "current_task_index": st.session_state.current_task_index,
        "classifier_output": st.session_state.classifier_output
    }

    # Invoke graph
    state = app.invoke(state)

    # Capture last assistant message and show
    print("invoked done")
    assistant_reply = state["messages"][-1].content
    with st.chat_message("assistant"):
        response = st.write_stream(response_generator(assistant_reply))
        #st.write(assistant_reply)

    # Update session state
    st.session_state.messages = state["messages"]
    st.session_state.checklist = state["checklist"]
    st.session_state.current_task_index = state["current_task_index"]
    st.session_state.classifier_output = state["classifier_output"]

    # End conversation if needed
    if state["current_task_index"] >= len(state["checklist"]):
        st.success("🎉 All tasks completed!")
