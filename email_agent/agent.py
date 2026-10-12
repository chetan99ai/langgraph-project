from dotenv import load_dotenv
load_dotenv()
# The import of os and getenv of groq ar eoptional because load env will load everything from .env file
# import os
# os.getenv("GROQ_API_KEY")

#### Import all the packages
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from send_email import send_email
import truststore
truststore.inject_into_ssl()

#### Define the LLM Object
# You can use gpt-oss-120b but it will be more costly beacuse it will be using too much memory more than our requirement of email agent
# 20b means it is capable of taking 20 b params
llm = ChatGroq(model="openai/gpt-oss-20b")

### Global State

class EmailState(BaseModel):
    question: str = ""
    mail_reason: str = ""
    recipient_name: str = ""
    recipient_email: str = ""
    subject: str = ""
    body: str = ""
    feedback: str = ""
    feedback_count: int = 0 ## Max Count 3
    response: str = ""

# The object of this class will be used by LLM to give structured o/p
class UserDetails(BaseModel):
    mail_reason: str = Field(description="Reason of the email, like why user want to send this email.")
    recipient_name: str = Field(description="recipient / reciever name, if available.")
    recipient_email: str = Field(description="recipient / reciever email address.")


#### Retriver Node
def retriever_node(state: EmailState) -> EmailState:
    prompt = f"""
        Retrive the user details from this query: {state.question}.
    """
    llm_for_user_details = llm.with_structured_output(UserDetails)
    userDetails: UserDetails = llm_for_user_details.invoke(prompt)

    if not userDetails.mail_reason or not userDetails.recipient_email:
        pass

    state.recipient_name = userDetails.recipient_name
    state.recipient_email = userDetails.recipient_email
    state.mail_reason = userDetails.mail_reason

    return state

#### Draft Node
class DraftEmail(BaseModel):
    subject: str = Field(description="Email subject within 40 Words")
    body: str = Field(description="Email Body including proper details, reason and greetings and others")

def draft_node(state: EmailState) -> EmailState:
    "Draft a Email"

    prompt = f"""
        Write a email with these details:
        To: {state.recipient_name}
        Request: {state.mail_reason}

        Please write a peoper mail body and subject. Without extra text. Mail body
        max size will be 200 Words.
    """

    # When the approved gives any feedback then state.feedback will have the feedback text in that.
    # When state.feedback is populated then a new promt will be given to llm along with the last email written by LLM on which the feedback was given.
    if state.feedback:
        prompt = f"""
                Revise this email based on the feedback below.
                Current Email:
                Subject: {state.subject}
                Body: {state.body}

                Feedback: {state.feedback}
        
                Please write a peoper mail body and subject. Without extra text. Mail body
                max size will be 200 Words.
            """

    draft_email_llm = llm.with_structured_output(DraftEmail)
    draft_email: DraftEmail = draft_email_llm.invoke(prompt)
    state.subject = draft_email.subject
    state.body = draft_email.body

    return state


#### Review Node

def review_node(state: EmailState) -> EmailState:
    print("\n")
    print("-"*50)
    print("Subject: ", state.subject, "\n")
    print("Body:", state.body)
    print("-"*50)

    response = interrupt({
        "message": "You want to approve this or re-write this email"
    })

    if response == "yes":
        state.feedback = ""
    else:
        state.feedback = response
        state.feedback_count = state.feedback_count + 1

    return state

def review_router(state: EmailState) -> Literal["draft", "send", "cancel"]:
    if not state.feedback or state.feedback.strip() == "":
        return "send"

    if state.feedback_count > 2:
        return "cancel"

    return "draft"

def cancel_node(state: EmailState) -> EmailState:
    "Cancel email sending"
    state.response = "Email Not Sent, Because you have reached the limit of feedbacks."
    return state

def send_node(state: EmailState) -> EmailState:
    "Send final email"
    response = send_email(state.recipient_email, state.subject, state.body)
    state.response = response
    return state

graph = StateGraph(EmailState)
graph.add_node("retriever", retriever_node)
graph.add_node("draft_node", draft_node)
graph.add_node("send_node", send_node)
graph.add_node("cancel_node", cancel_node)
graph.add_node("review_node", review_node)

graph.add_edge(START, "retriever")
graph.add_edge("retriever", "draft_node")
graph.add_edge("draft_node", "review_node")
graph.add_conditional_edges(
    "review_node",
    review_router,
    {
        "draft": "draft_node",
        "send": "send_node",
        "cancel": "cancel_node"
    })
# graph.add_conditional_edges("review_node", review_router)
graph.add_edge("send_node", END)
graph.add_edge("cancel_node", END)

final_graph = graph.compile(checkpointer=InMemorySaver())

while True:
    query = input("User: ")
    if query == "quit":
        print("Bye !")
        break

    config = {"configurable": {"thread_id": "email_agent_conv_thrd_5"}}
    res = final_graph.invoke(
        {
            "question": query
        },
        config=config
    )

    while True:
        state = final_graph.get_state(config)

        if not state.next:
            break

        print("\n", "-"*60)
        print("Subject: ", res["subject"])
        print("Body: ", res["body"])
        print("\n", "-"*60)
        feedback = input("Say yes if you want to approve the current draft or provide feedback:")

        res = final_graph.invoke(
            Command(resume=feedback),
            config=config
        )

    print("AI: ", res["response"])