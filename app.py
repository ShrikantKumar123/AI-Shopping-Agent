
"""Streamlit UI for the AI Shopping Agent with authentication."""

import os

import streamlit as st

from agent import build_agent, chat, ensure_database

from auth import (
    authenticate_user,
    initialize_auth,
    register_user,
)

from memory import (
    create_conversation,
    delete_conversation,
    get_messages,
    initialize_memory,
    list_conversations,
    save_message,
)


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="AI Shopping Agent",
    page_icon="🛒",
    layout="wide",
)


SAMPLE_QUESTIONS = [
    "Find me organic honey under $20 with 4.5+ rating",
    "Show organic snacks under $10",
    "What's the best rated coffee?",
    "Find dairy alternatives rated 4.5 or higher",
    "Cheapest grains you have?",
]


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

ensure_database()
initialize_memory()
initialize_auth()


# --------------------------------------------------
# Agent initialization
# --------------------------------------------------

@st.cache_resource
def get_agent():
    """Create and cache the shopping agent."""
    return build_agent()


# --------------------------------------------------
# Session state initialization
# --------------------------------------------------

def initialize_session_state():
    """Initialize application session state."""

    defaults = {
        "user": None,
        "conversation_id": None,
        "messages": [],
        "selected_conversation": None,
        "pending_question": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def login_user(user):
    """Initialize session after successful login."""

    st.session_state.user = user

    # Reset previous conversation state.
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.selected_conversation = None
    st.session_state.pending_question = None


def logout_user():
    """Clear the authenticated user's session."""

    st.session_state.user = None
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.selected_conversation = None
    st.session_state.pending_question = None


def show_authentication_page():
    """Display login and registration forms."""

    st.title("🛒 AI Shopping Agent")

    st.caption(
        "Your personal AI shopping assistant. "
        "Log in or create an account to continue."
    )

    login_tab, register_tab = st.tabs(
        ["Login", "Create Account"]
    )

    # ---------------- Login ----------------

    with login_tab:

        st.subheader("Login to your account")

        with st.form("login_form"):

            email = st.text_input(
                "Email address",
                placeholder="Enter your email",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button(
                "Login",
                use_container_width=True,
                type="primary",
            )

        if submitted:

            if not email.strip() or not password:
                st.error("Please enter your email and password.")

            else:

                try:
                    result = authenticate_user(
                        email=email,
                        password=password,
                    )

                    if result["success"]:
                        login_user(result["user"])
                        st.rerun()

                    else:
                        st.error(result["message"])

                except Exception:
                    st.error(
                        "Unable to log in right now. Please try again."
                    )

    # ---------------- Registration ----------------

    with register_tab:

        st.subheader("Create a new account")

        with st.form("register_form"):

            name = st.text_input(
                "Full name",
                placeholder="Enter your name",
            )

            email = st.text_input(
                "Email address",
                placeholder="Enter your email",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Minimum 8 characters",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                placeholder="Re-enter your password",
            )

            submitted = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary",
            )

        if submitted:

            if not name.strip() or not email.strip():
                st.error("Please fill in all required fields.")

            elif not password or not confirm_password:
                st.error("Please enter and confirm your password.")

            elif password != confirm_password:
                st.error("Passwords do not match.")

            else:

                try:
                    result = register_user(
                        name=name,
                        email=email,
                        password=password,
                    )

                    if result["success"]:
                        st.success(
                            "Account created successfully! "
                            "Please log in."
                        )

                    else:
                        st.error(result["message"])

                except Exception:
                    st.error(
                        "Unable to create your account. "
                        "Please try again."
                    )


# --------------------------------------------------
# Conversation initialization
# --------------------------------------------------

def initialize_chat_session():
    """Create or restore the current user's conversation."""

    user_id = st.session_state.user["id"]

    if not st.session_state.conversation_id:

        conversation_id = create_conversation(user_id)

        st.session_state.conversation_id = conversation_id
        st.session_state.messages = []


# --------------------------------------------------
# Conversation callbacks
# --------------------------------------------------

def start_new_chat():
    """Start a new conversation for the logged-in user."""

    user_id = st.session_state.user["id"]

    conversation_id = create_conversation(user_id)

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = []
    st.session_state.selected_conversation = None
    st.session_state.pending_question = None


def delete_current_chat():
    """Delete the current user's conversation."""

    user_id = st.session_state.user["id"]

    conversation_id = st.session_state.get("conversation_id")

    if conversation_id:

        delete_conversation(
            conversation_id,
            user_id,
        )

    # Create a fresh conversation.
    new_conversation_id = create_conversation(user_id)

    st.session_state.conversation_id = new_conversation_id
    st.session_state.messages = []
    st.session_state.selected_conversation = None


def load_selected_conversation():
    """Load a selected conversation owned by the current user."""

    user_id = st.session_state.user["id"]

    selected_id = st.session_state.selected_conversation

    if not selected_id:
        return

    messages = get_messages(
        selected_id,
        user_id,
    )

    st.session_state.conversation_id = selected_id
    st.session_state.messages = messages


def set_pending_question(question):
    """Set a sample question to be sent to the agent."""

    st.session_state.pending_question = question


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

def show_sidebar():

    user_id = st.session_state.user["id"]

    with st.sidebar:

        # User information
        st.markdown(
            f"### Welcome, {st.session_state.user['name']}!"
        )

        st.caption(st.session_state.user["email"])

        st.button(
            "Logout",
            use_container_width=True,
            on_click=logout_user,
        )

        st.divider()

        # New chat
        st.markdown("### Conversation history")

        st.button(
            "➕ New chat",
            use_container_width=True,
            type="primary",
            on_click=start_new_chat,
        )

        # Get only this user's conversations.
        conversations = list_conversations(user_id)

        conversation_lookup = {
            item["id"]: item
            for item in conversations
        }

        conversation_ids = [
            item["id"]
            for item in conversations
        ]

        # Reset selection if the selected conversation no longer exists.
        if (
            st.session_state.selected_conversation is not None
            and st.session_state.selected_conversation not in conversation_ids
        ):
            st.session_state.selected_conversation = None

        # Conversation selector
        st.selectbox(
            "Previous chats",
            options=[None] + conversation_ids,
            format_func=lambda value: (
                "Choose a conversation..."
                if value is None
                else conversation_lookup[value]["title"]
            ),
            key="selected_conversation",
            on_change=load_selected_conversation,
        )

        # Delete current conversation
        if st.session_state.messages:

            st.button(
                "🗑️ Delete current chat",
                use_container_width=True,
                on_click=delete_current_chat,
            )

        st.divider()

        # Sample questions
        st.markdown("#### Try asking")

        for index, question in enumerate(SAMPLE_QUESTIONS):

            st.button(
                question,
                key=f"sample_question_{index}",
                use_container_width=True,
                on_click=set_pending_question,
                args=(question,),
            )


# --------------------------------------------------
# Main chat interface
# --------------------------------------------------

def show_chat_page():

    st.title("🛒 AI Shopping Agent")

    st.caption(
        "Search products, compare items, manage your cart, "
        "and place orders using natural language."
    )

    # Check Groq API key
    if not os.getenv("GROQ_API_KEY"):

        st.error(
            "GROQ_API_KEY is not set. "
            "Add it to your `.env` file in the project root."
        )

        st.stop()

    # Display existing conversation messages
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    prompt = st.chat_input(
        "Ask for a product or place an order..."
    )

    # Use sample question if chat input is empty.
    if not prompt:

        prompt = st.session_state.pending_question

    # Clear pending sample question.
    if prompt:
        st.session_state.pending_question = None

    if not prompt:
        return

    user_id = st.session_state.user["id"]
    conversation_id = st.session_state.conversation_id

    # ---------------- User message ----------------

    user_message = {
        "role": "user",
        "content": prompt,
    }

    st.session_state.messages.append(user_message)

    save_message(
        conversation_id,
        user_id,
        "user",
        prompt,
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # ---------------- Assistant response ----------------

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            try:

                reply = chat(
                    get_agent(),
                    st.session_state.messages,
                    user_id=int(st.session_state.user["id"])
                )

            except Exception as error:

                # Keep technical details in terminal logs.
                print(f"Agent error: {error}")

                reply = (
                    "Sorry, something went wrong while "
                    "processing your request. Please try again."
                )

        st.markdown(reply)

    # Save assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )

    save_message(
        conversation_id,
        user_id,
        "assistant",
        reply,
    )


# --------------------------------------------------
# Application entry point
# --------------------------------------------------

def main():

    # Show login/register page if not authenticated.
    if st.session_state.user is None:

        show_authentication_page()

        return

    # Initialize conversation after login.
    initialize_chat_session()

    # Render sidebar and chat.
    show_sidebar()

    show_chat_page()


if __name__ == "__main__":
    main()
