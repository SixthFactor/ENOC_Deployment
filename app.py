import streamlit as st
import openai
import os
from dotenv import load_dotenv
import time
import uuid
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_PytLeS8CwhZiswnc11HCsmbO")
ASSISTANT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Rely solely on the supplied knowledge base. "
    "If the answer isn’t there, reply: ‘I’m sorry, that information isn’t in my database. "
    "Please re-ask using topics the database covers. Keep every reply directly focused on the question. "
    "Present the reply as a numbered or bulleted list.’"
)
POLLING_INTERVAL = 1

# UI Styling
st.set_page_config(page_title="AI Assistant Chat", page_icon="🤖", layout="wide")
st.markdown("""
    <div style='text-align:center; margin-top: 10px; margin-bottom: 30px;'>
        <h1 style='color: #004aad;'>ENOC Bot: Your Smart Assistant</h1>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.error-box {
    background: #f8d7da;
    color: #721c24;
    padding: 0.75rem;
    border-radius: 6px;
    margin: 0.5rem 0;
    border-left: 4px solid #dc3545;
}
.stChatInput {
    margin-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

# Logging
logging.basicConfig(filename='openai_logs.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

# OpenAI key
openai.api_key = OPENAI_API_KEY

# Allowed users
ALLOWED_USERS = {
    "admin": "1234",
    "deepak": "1234"
}

# Session state init
def initialize_session_state():
    defaults = {
        'chats': {},
        'current_chat_id': None,
        'client': None,
        'last_error': None,
        'is_responding': False,
        'current_message_placeholder': None,
        'logged_in': False,
        'username': None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# Chat functions
def create_new_chat():
    chat_id = str(uuid.uuid4())
    chat_title = f"New chat {datetime.now().strftime('%H:%M')}"
    st.session_state.chats[chat_id] = {
        'id': chat_id,
        'title': chat_title,
        'messages': [],
        'thread_id': None,
        'created_at': datetime.now()
    }
    st.session_state.current_chat_id = chat_id

def get_current_chat():
    return st.session_state.chats.get(st.session_state.current_chat_id)

def update_chat_title(chat_id, title):
    if chat_id in st.session_state.chats:
        st.session_state.chats[chat_id]['title'] = title

# OpenAI calls
def setup_openai_client(api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return client
    except Exception as e:
        st.error(f"Error connecting to OpenAI: {str(e)}")
        return None

def create_or_get_thread(client, assistant_id, chat):
    try:
        if chat['thread_id'] is None:
            thread = client.beta.threads.create()
            chat['thread_id'] = thread.id
        return chat['thread_id']
    except Exception as e:
        st.error(f"Error creating thread: {str(e)}")
        return None

def cancel_active_run(client, thread_id):
    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        for run in runs.data:
            if run.status in ["queued", "in_progress"]:
                client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
    except:
        pass

def send_message(client, thread_id, message):
    try:
        cancel_active_run(client, thread_id)
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=message)
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID, instructions=ASSISTANT_SYSTEM_PROMPT)
        return run.id
    except Exception as e:
        st.session_state.last_error = str(e)
        return None

def get_run_status(client, thread_id, run_id):
    try:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status == "failed":
            st.session_state.last_error = getattr(run, 'last_error', None) or getattr(run, 'error', None)
        return run.status
    except Exception as e:
        st.session_state.last_error = str(e)
        return None

def get_assistant_response(client, thread_id):
    try:
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        return messages.data[0].content[0].text.value
    except Exception as e:
        st.session_state.last_error = str(e)
        st.error(f"Error getting response: {str(e)}")
        return None

# Stream response
def stream_response(placeholder, response):
    full_response = ""
    for char in response:
        if not st.session_state.is_responding:
            return full_response
        full_response += char
        placeholder.markdown(full_response + "▌")
        time.sleep(0.005)
    placeholder.markdown(full_response)
    return full_response

# Log interaction locally
def log_openai_interaction(prompt, assistant_response, username):
    try:
        logging.info("===== New Interaction =====")
        logging.info(f"User: {username}")
        logging.info(f"Prompt: {prompt}")
        logging.info(f"Response: {assistant_response}")
        logging.info("===========================")
    except Exception as e:
        logging.error(f"Logging error: {e}")

# Main app
def main():
    initialize_session_state()

    if st.session_state.client is None:
        st.session_state.client = setup_openai_client(OPENAI_API_KEY)
        if st.session_state.client is None:
            st.error("❌ Failed to initialize OpenAI client. Please check your API key.")
            return

    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.title("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if username in ALLOWED_USERS and password == ALLOWED_USERS[username]:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        return

    if not st.session_state.current_chat_id:
        create_new_chat()

    current_chat = get_current_chat()
    for msg in current_chat['messages']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Type your message here...")
    if prompt:
        username = st.session_state.get("username", "unknown")

        log_openai_interaction(prompt, "", username)

        if st.session_state.is_responding:
            st.session_state.is_responding = False
            if st.session_state.current_message_placeholder:
                st.session_state.current_message_placeholder.markdown("⚠️ Response interrupted.")

        current_chat['messages'].append({"role": "user", "content": prompt})
        if len(current_chat['messages']) == 1:
            update_chat_title(current_chat['id'], prompt[:30] + "..." if len(prompt) > 30 else prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            st.session_state.current_message_placeholder = message_placeholder
            st.session_state.is_responding = True

            thread_id = create_or_get_thread(st.session_state.client, ASSISTANT_ID, current_chat)
            if thread_id:
                run_id = send_message(st.session_state.client, thread_id, prompt)
                if run_id:
                    with st.spinner("🤔 Thinking..."):
                        while True:
                            if not st.session_state.is_responding:
                                break
                            status = get_run_status(st.session_state.client, thread_id, run_id)
                            if status == "completed":
                                response = get_assistant_response(st.session_state.client, thread_id)
                                if response:
                                    log_openai_interaction(prompt, response, username)
                                    try:
                                        openai.chat.completions.create(
                                            model="gpt-4",
                                            messages=[
                                                {"role": "system", "content": f"Interaction from user: {username}"},
                                                {"role": "user", "content": prompt},
                                                {"role": "assistant", "content": response}
                                            ],
                                            temperature=0,
                                            max_tokens=1
                                        )
                                    except Exception as e:
                                        logging.warning(f"Failed to shadow-log to OpenAI: {e}")

                                    stream_response(message_placeholder, response)
                                    if st.session_state.is_responding:
                                        current_chat['messages'].append({"role": "assistant", "content": response})
                                break
                            elif status in ["queued", "in_progress"]:
                                time.sleep(POLLING_INTERVAL)
                            else:
                                message_placeholder.markdown("⚠️ Error. Please try again.")
                                break

        st.session_state.is_responding = False
        st.session_state.current_message_placeholder = None

if __name__ == "__main__":
    main()
