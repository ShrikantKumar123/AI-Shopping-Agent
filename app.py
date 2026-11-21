
"""Streamlit UI for the AI shopping agent."""

import os
import streamlit as st

from agent import build_agent, chat, ensure_database
from memory import (
    create_conversation,
    delete_conversation,
    get_messages,
    initialize_memory,
    list_conversations,
    save_message,
)

st.set_page_config(page_title="AI Shopping Agent", page_icon="🛒")

SAMPLE_QUESTIONS = [
    "Find me organic honey under $20 with 4.5+ rating",
    "Show organic snacks under $10",
    "What's the best rated coffee?",
    "Find dairy alternatives rated 4.5 or higher",
    "Cheapest grains you have?",
]


@st.cache_resource
def get_agent():
    return build_agent()


# Initialize the product database BEFORE opening it for conversation memory.
ensure_database()
initialize_memory()


# Initialize session state.
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = create_conversation()

if "messages" not in st.session_state:
    st.session_state.messages = get_messages(
        st.session_state.conversation_id
    )

if "selected_conversation" not in st.session_state:
    st.session_state.selected_conversation = None


# ---------- Callback functions ----------

def start_new_chat():
    """Create a new conversation."""
    st.session_state.conversation_id = create_conversation()
    st.session_state.messages = []
    st.session_state.selected_conversation = None


def delete_current_chat():
    """Delete the current conversation and create a fresh one."""
    conversation_id = st.session_state.get("conversation_id")

    if conversation_id:
        delete_conversation(conversation_id)

    st.session_state.conversation_id = create_conversation()
    st.session_state.messages = []
    st.session_state.selected_conversation = None


# ---------- Sidebar ----------

with st.sidebar:

    st.markdown("### Conversation history")

    st.button(
        "➕ New chat",
        use_container_width=True,
        type="primary",
        on_click=start_new_chat,
    )

    conversations = list_conversations()

    conversation_lookup = {
        item["id"]: item for item in conversations
    }

    conversation_ids = [
        item["id"] for item in conversations
    ]

    # Reset stale selection before creating the widget.
    if st.session_state.selected_conversation not in [
        None, *conversation_ids
    ]:
        st.session_state.selected_conversation = None

    selected_id = st.selectbox(
        "Previous chats",
        options=[None] + conversation_ids,
        format_func=lambda value: (
            "Choose a conversation..."
            if value is None
            else conversation_lookup[value]["title"]
        ),
        key="selected_conversation",
    )

    # Restore an existing conversation.
    if (
        selected_id
        and selected_id != st.session_state.conversation_id
    ):
        st.session_state.conversation_id = selected_id
        st.session_state.messages = get_messages(selected_id)
        st.rerun()

    # Delete current conversation.
    if st.session_state.messages:
        st.button(
            "🗑️ Delete current chat",
            use_container_width=True,
            on_click=delete_current_chat,
        )

    st.divider()

    st.markdown("#### Try asking")

    pending = None

    for question in SAMPLE_QUESTIONS:
        if st.button(question, use_container_width=True):
            pending = question


# ---------- Main ----------

st.title("🛒 AI Shopping Agent")

st.caption(
    "Search products and place orders by chatting. "
    "Your conversations are saved locally."
)

if not os.getenv("GROQ_API_KEY"):
    st.error(
        "GROQ_API_KEY is not set. "
        "Add it to a `.env` file in the project root."
    )
    st.stop()


# Display conversation messages.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Accept user input.
prompt = st.chat_input(
    "Ask for a product or place an order…"
) or pending


if prompt:

    user_message = {
        "role": "user",
        "content": prompt
    }

    st.session_state.messages.append(user_message)

    save_message(
        st.session_state.conversation_id,
        "user",
        prompt
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        with st.spinner("Thinking…"):
            try:
                reply = chat(
                    get_agent(),
                    st.session_state.messages
                )

            except Exception as error:
                reply = f"Sorry, something went wrong: `{error}`"

        st.markdown(reply)

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply
    })

    save_message(
        st.session_state.conversation_id,
        "assistant",
        reply
    )
