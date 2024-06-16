import gradio as gr
import ollama
from pathlib import Path
import os
import sys
from dotenv import load_dotenv

from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama

from nemoguardrails import RailsConfig, LLMRails

# Load environment variables
load_dotenv()
print(f"ENV_PROD: {os.environ.get('ENV_PROD')}")

# Parse and set env to (DEV) or (PRODUCTION)
env_prod = os.environ.get('ENV_PROD') == 'True'

# Initialize Ollama LLM with LLaMA3:8B (DEV) or LLaMA3:70B (PRODUCTION)
model_name = "llama3:70b" if env_prod else "llama3:8b"
ollama_llm = Ollama(model=model_name)
print(f"Load LLM Model: {model_name}")

# Dynamically generate the guardrails configuration content
guardrails_config_content = f"""
models:
  - name: main_model
    type: llm
    provider: ollama
    model: {model_name}
    engine: ollama

user_messages:
  greeting: ["Hello!", "Hi!", "How are you?"]

bot_messages:
  greeting_response: ["I'm good, thank you! How can I help you today?"]

flows:
  - id: greet_user
    elements:
      - action: user_says_greeting
      - action: bot_says_greeting_response
"""

# Write the dynamically generated content to the configuration file
guardrails_config_path = Path("guardrails_config.yaml")
guardrails_config_path.write_text(guardrails_config_content)
print(f"Guardrails configuration written to {guardrails_config_path}")


# Load guardrails configuration
try:
    config = RailsConfig.from_content(yaml_content=guardrails_config_content)
    rails = LLMRails(config)
    print("Guardrails configuration loaded successfully.")
    
    # Print out the attributes of the rails object to check for initialization issues
    #print(f"LLMRails attributes: {dir(rails)}")
except Exception as e:
    print(f"Error loading guardrails configuration: {e}")
    sys.exit(1)

# Check if the rails object is properly initialized
if rails is None:
    print("Failed to initialize guardrails.")
    sys.exit(1)

# Define the prompt template
prompt = PromptTemplate(template="Question: {question}\nAnswer:", input_variables=["question"])

# Create the LangChain with the model
langchain_chain = LLMChain(llm=ollama_llm, prompt=prompt)

def format_history(msg: str, history: list[list[str, str]], system_prompt: str):
    chat_history = [{"role": "system", "content": system_prompt}]
    for query, response in history:
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": response})
    chat_history.append({"role": "user", "content": msg})
    return chat_history

def generate_response(msg: str, history: list[list[str, str]], system_prompt: str):
    try:
        chat_history = format_history(msg, history, system_prompt)
        
        # Apply guardrails middleware
        filtered_input = guardrails_middleware(msg)
        if filtered_input == "This question is not allowed.":
            return filtered_input
        
        response = ollama.chat(model=model_name, stream=True, messages=chat_history)
        message = ""
        for partial_resp in response:
            token = partial_resp["message"]["content"]
            message += token
            yield message

        # Process with LangChain
        return langchain_chain.invoke({"question": filtered_input})
    except Exception as e:
        print(f"Error during response generation: {e}")
        return "I'm sorry, an internal error has occurred."

def guardrails_middleware(input_text):
    try:
        print(f"Guardrails Middleware Input: {input_text}")
        response = rails.generate(messages=[{
            "role": "user",
            "content": input_text
        }])
        print(f"Guardrails Middleware Response: {response}")
        
        # Example response handling, customize based on actual response structure
        if response.get("content") == "This question is not allowed.":
            return "This question is not allowed."
        else:
            return input_text
    except AttributeError as ae:
        print(f"AttributeError in guardrails middleware: {ae}")
        return "I'm sorry, an internal error has occurred."
    except Exception as e:
        print(f"Error in guardrails middleware: {e}")
        return "I'm sorry, an internal error has occurred."

chatbot = gr.ChatInterface(
    generate_response,
    chatbot=gr.Chatbot(
        avatar_images=["img/user.png", "img/chatbot.png"],
        height="64vh"
    ),
    additional_inputs=[
        gr.Textbox(
            "Behave as if you are professional writer.",
            label="System Prompt"
        )
    ],
    title=f"Chatbot using Ollama with {model_name}",
    description="Feel free to ask any question.",
    theme="soft",
    submit_btn="⬅ Send",
    retry_btn="🔄 Regenerate Response",
    undo_btn="↩ Delete Previous",
    clear_btn="🗑️ Clear Chat"
)

chatbot.launch(share=env_prod)
