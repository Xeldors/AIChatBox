from pyngrok import ngrok
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from random import choices
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import inspect
import os
from datetime import datetime
import threading
from werkzeug.utils import secure_filename
import random
import asyncio
import openai
from chat_with_me import chat_with_me
import concurrent.futures

db_folder = "PLACE TO STORE THE DATABASE"
os.makedirs(db_folder, exist_ok=True)  # Ensure the folder exists


app = Flask(__name__,
            template_folder='./templates',
            static_folder='./static')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_folder}/chat_mx.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bcrypt = Bcrypt(app)

#Creat taks logs
tasks = {}

# Initialize Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class chat(db.Model):
    __tablename__ = 'output'
    id = db.Column(db.String(300), primary_key=True, default=''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28)))
    input = db.Column(db.Text, nullable=False)
    output = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(300), nullable=False)  

class api_status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(300), nullable=False, info={'encrypted': True})  
    model = db.Column(db.String(300), nullable=False) 
    key = db.Column(db.String(300), nullable=False, info={'encrypted': True}) 
    api_status = db.Column(db.Integer, nullable=False, default=0)
    Usage = db.Column(db.Integer, nullable=False) 


with app.app_context():
    db.create_all()




def run_async_in_thread(async_func, *args, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func(*args, **kwargs))
    loop.close()


@app.route('/')
def home():
    return render_template('chat_frontend.html')

@app.route('/chat_sent/<chat_id>', methods=['POST'])
def chat_sent(chat_id):
    ##Part 1 getting input from frontend
    input_text = request.form['input_text']
    model = request.form['model']
    # chat_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28))
    chat_id = request.form['chat_id'] 
    
    existing_chat = chat.query.filter_by(id=chat_id).first()
    if existing_chat:
        existing_chat.input = input_text
        existing_chat.output = "¡Estamos pensandon... carajo!"
        existing_chat.model = model
        db.session.commit()
        new_chat = existing_chat
    else:
        new_chat = chat(input=input_text, output="¡Estamos pensandon... carajo!", model=model, id=chat_id)
        db.session.add(new_chat)
        db.session.commit()

    #Part 2 assigns a free api key to the task
    GPT_API = api_status.query.filter_by(provider='openai', api_status=0 ).first()

    #Part 3  Initialise the task and task log
    task_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28))
    tasks[task_id] = {'status': 'processing', 'input': input_text, 'model': model}
    # Start a new thread to process the task
    
    threading.Thread(
        target=run_async_in_thread,
        args=(chat_with_me, tasks, task_id, model, GPT_API.key, chat_id)
    ).start()

    
    return jsonify({'chat_box': new_chat.output, })


@app.route('/chat_get/<chat_id>', methods=['POST'])
def chat_receive(chat_id):
    chat_id = request.form['chat_id']   
    chat_new= chat.query.filter_by(id=chat_id).first()
    return jsonify({'chat_box': chat_new.output, })


@app.route('/tasks', methods=['GET'])
def get_tasks():
    return jsonify(tasks)

# http://localhost:5000/tasks

os.system('taskkill /f /im ngrok.exe')  # Kill any existing ngrok processes
ngrok.set_auth_token("your_ngrok_auth_token")  # Set your ngrok auth token here
public_url = ngrok.connect(5000)
print(f" * Ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")

if __name__ == '__main__':
    app.run(debug=True)
