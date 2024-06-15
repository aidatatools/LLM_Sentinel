import gradio as gr
import ollama
from pathlib import Path

from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama

from nemoguardrails import RailsConfig, LLMRails

# Initialize Ollama LLM with LLaMA3:8B (DEV) or LLaMA3:70B (PRODUCTION)
ollama_llm = Ollama(model="llama3:8b")

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
    
    response = ollama.chat(model='llama3:8b', stream=True, messages=chat_history)
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
                title="LLama-3 (8B) Chatbot using 'Ollama'",
                description="Feel free to ask any question.",
                theme="soft",
                submit_btn="⬅ Send",
                retry_btn="🔄 Regenerate Response",
                undo_btn="↩ Delete Previous",
                clear_btn="🗑️ Clear Chat"
)

chatbot.launch()