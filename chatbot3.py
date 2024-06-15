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

load_dotenv()
print(f"ENV_PROD:{os.environ['ENV_PROD']}")

# Parse and set env to (DEV) or (PRODUCTION)
if (os.environ['ENV_PROD']=='True'):
    env_prod = True
else:
    env_prod = False

# Initialize Ollama LLM with LLaMA3:8B (DEV) or LLaMA3:70B (PRODUCTION)
if (env_prod==True):
    model_name = "llama3:70b"
    ollama_llm = Ollama(model=model_name)
else: 
    model_name = "llama3:8b"
    ollama_llm = Ollama(model=model_name)

print(f"Load LLM Model : {model_name}")

# Load guardrails configuration
config = RailsConfig.from_content(yaml_content=Path("guardrails_config.yaml").read_text())
rails = LLMRails(config)

# Define the prompt template
prompt = PromptTemplate(template="Question: {question}\nAnswer:", input_variables=["question"])

# Create the LangChain with the model
langchain_chain = LLMChain(llm=ollama_llm, prompt=prompt)

def format_history(msg: str, history: list[list[str, str]], system_prompt: str):
    chat_history = [{"role": "system", "content":system_prompt}]
    for query, response in history:
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": response})  
    chat_history.append({"role": "user", "content": msg})
    return chat_history

def generate_response(msg: str, history: list[list[str, str]], system_prompt: str):
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


def guardrails_middleware(input_text):
    response = rails.generate(messages=[{
        "role": "user",
        "content": input_text
    }])
    print(response)
    # if guardrails.input_text):
    #     return "This question is not allowed."
    # else:
    #     return input_text


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
                title= f"Chatbot using Ollama with {model_name} ",
                description="Feel free to ask any question.",
                theme="soft",
                submit_btn="⬅ Send",
                retry_btn="🔄 Regenerate Response",
                undo_btn="↩ Delete Previous",
                clear_btn="🗑️ Clear Chat"
)
if (env_prod==True):
    chatbot.launch(share=True)
else:
    chatbot.launch()