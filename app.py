# /// script
# requires-python = ">=3.12"
# dependences = [
#    "fastapi",
#    "uvicorn",
#    "requests",
# ]
# ///

from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Ensure this import is correct
from fastapi.responses import StreamingResponse
from fastapi.resonses import JSONResponse
import mimetypes
from pathlib import Path
from dateutil import parser
import numpy as np
from typing import Dict, Any
import base64
from sklearn.metrics.pairwise import cosine_similarity
import requests
import os
import subprocess
from subprocess import run
import json
import pandas as pd

app = FastAPI()

response_format = {
    "type": "json_schema",
    "json_scheme":{
        "name":"task_runner",
        "schema":{
            "type":"object",
            "required":["python_dependencies","python_code"]
            "properties":{
                "python_code":{
                    "type":"string",
                    "description":"Python code to perform a task"              
                },
                {
                    "python_dependencies":{
                        "type":"array",
                        "items":{
                            "type":"object",
                            "properties":{
                                "module":{
                                    "type":"string"
                                    "description":"Name of python module"
                                }
                            },
                            "required":["module"],
                            "additionalProperties":False
                        }
                    }
                }
            }
        }
    }
}


primary_prompt = """"
you are an automated agent, so generate python code that does the specified task.
Assume uv and python is preinstalled.
Assume that code you generate will be executed inside a docker container.
if you need to run any uv script thenuse 'uv run {name of script} arguments'.
Even if the date and time in a file are in differentformate, you have to modify them into single format and process
Inorder to performance any task if some python package is required to install, provide name of those modules.
"""

app.add_middleware(
    CORSMiddleware,  # Use the correct class name here
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

AIPROXY_TOKEN=os.getenv("AIPROXY_TOKEN")

SCRIPT_RUNNER = {
        "type": "function",
        "function": {
            "name": "script_runner",
            "description": "Install a package and run a script from a URL with provided arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_url": {
                        "type": "string",
                        "description": "The URL of the script to run."
                    },
                    "args": {
                        "type": "array",
                        "items": {  # Missing colon fixed here
                            "type": "string"
                        },
                        "description": "List of arguments to pass to the script"
                    }
                },
                "required": ["script_url", "args"]
            }
        }
    }
]

SORTED_CONTACTS = {
    {
        "type": "function",
        "function": {
            "name": "sorted_contacts",
            "description": "This function takes data from a json file and sorts the data first by lastname and then by first name, then it stores it inside the specified location",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_location": {
                        "type": "string",
                        "description": "The relative location of the input file"
                    },
                    "output_location": {
                        "type": "string",                     
                        "description": "The relative location of the output file"
                    },
                },
                "required": ["input_location", "output_location"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    }
}

tools = [SCRIPT_RUNNER,SORTED_CONTACTS]
@app.get("/")
def home():
    return "Yay TDS done. Good Job"

@app.get("/read")
def read_file(path:str):
    try:
        with open(path,"r") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
@app.post("/run")
def task_runner(task:str):
    url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    headers = {
        "Content-type": "application/json",
        "Authorization":f"Bearer{AIPROXY_TOKEN}"
    }
    data = {
        "model":"gpt-4o-mini",
        "messages":[
            {
                "role":"user",
                "content":task
            },
            {
                "role":"system",
                "content":"""You are an assistant who has to do a variety of tasks
                if your task involves running a script, you can use the script_runner tool.
                If your task involves writing a code, you can use the task_runner tool. Also, whenever you 
                receive a system directory location, always make it into a relative path, for example adding a . before it would make it relative path,
                rest is on you to manage, i just want the relative path."""
            },

                {
                "role":"system",
                "content":f"""{primary_prompt}"""
            }
        ],
        "response_format":response_format
        "tools":tools,
        "tool_choice":"auto"
    }
    
    response = requests.post(url=url,headers=headers,json = data)
    response_data = requests.post(url=url,headers=headers,json = data)

    r = response.json()
 
    python_dependencies = json.loads(r['choices'][0]['message']['content'])['python_dependencies']
    inline_metadata_script = """
# /// script
# requires-python = ">=3.12"
# dependences = [
{''.join(f"#\"{dependency['module']}\",\n" for dependency in python_dependencies)}#]
# ///
"""

    python_code = json.loads(r['choices'][0]['message']['content'])['python_code']
    with open("llm_code.py","w") as f:
        f.write(inline_metadata_script)
        f.write(python_code)
    
    output = run("uv,"run","llm_code.py)
    # Navigate the JSON safely
    tool_calls = response_data.get('choices', [{}])[0].get('message', {}).get('tool_calls', [{}])

    if tool_calls and 'function' in tool_calls[0]:
        function_data = tool_calls[0]['function']

        # Ensure function_data is a string before parsing
        if isinstance(function_data, str):
            function_data = json.loads(function_data)  # Convert JSON string to dictionary

        arguments = function_data.get('arguments', {})  # Safely access 'arguments'
    else:
        arguments = {}


    #arguments = json.loads(response.json()['choices'][0]['message']['tool_calls'][0]['function'])['arguments']
    #script_url = arguments['script_url']
    script_url = arguments.get('script_url', '')
    email = arguments['args'][0]
    command = ["uv","run",script_url,email]
    subprocess.run(command)

def sorted_contacts(input_location:str, output_location:str):
    contacts = pd.read_json(input_location)
    contacts.sort_values(["last_name","first_name"]).to_json(output_location,orient="records")
    return {"status": "Successfully Created", "output_file destination": output_location}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)