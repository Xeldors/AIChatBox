from pyngrok import ngrok
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import JSON
from sqlalchemy.orm.attributes import flag_modified
import os
import threading
import random
import asyncio
from chat_with_me_local import chat_with_me_local

db_folder = r"folder_path"  # Change this to your desired folder path
os.makedirs(db_folder, exist_ok=True)  # Ensure the folder exists
os.system('taskkill /f /im ngrok.exe')

app = Flask(__name__,
            template_folder='./templates',
            static_folder='./static')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_folder}/chat_mx.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bcrypt = Bcrypt(app)

#Creat taks logs
tasks = {}
current_task_id=[]

# Initialize Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class chat(db.Model):
    __tablename__ = 'output'
    id = db.Column(db.String(300), primary_key=True, default=''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28)))
    input = db.Column(JSON, nullable=True)
    output = db.Column(JSON, nullable=True)
    model = db.Column(db.String(300), nullable=True)  


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


@app.route('/chat_id_api', methods=['GET'])
def chat_id_api():
    chat_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28))
    new_chat = chat(id=chat_id)
    db.session.add(new_chat)
    print(chat_id)
    db.session.commit()
    return jsonify({'chat_id': chat_id, })



@app.route('/chat_sent/<chat_id>', methods=['POST'])
def chat_sent(chat_id):
    ##Part 1 getting input from frontend
    input_text = request.form['input_text']
    model = "Llama Local"
    chat_id = request.form['chat_id'] 
    
    existing_chat = chat.query.filter_by(id=chat_id).first()
    print(existing_chat.input)
    if existing_chat.input != None:
        print("case2")
        lenghth_hist = len(existing_chat.input.keys())
        existing_chat.input[str(lenghth_hist)] = input_text
        flag_modified(existing_chat, "input")
        flag_modified(existing_chat, "output")
        existing_chat.model = model
        db.session.commit()
        new_chat = existing_chat
    else:
        lenghth_hist = 0
        print("case1")
        existing_chat.input = {str(lenghth_hist): input_text}
        existing_chat.model = model
        new_chat = existing_chat
    
    
    db.session.commit()
    
    print(chat_id)

    #Part 3  Initialise the task and task log
    task_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=[]{}|;:,.<>?', k=28))
    tasks[task_id] = {'status': 'processing', 'input': input_text, 'model': model}
    # Start a new thread to process the task
    
    threading.Thread(
        target=run_async_in_thread,
        args=(chat_with_me_local, tasks, task_id, chat_id, str(lenghth_hist)),
    ).start()

    return jsonify({'chat_box': "Thinking", }, task_id)


@app.route('/chat_get/<chat_id>', methods=['POST'])
def chat_receive(chat_id):
    chat_id = request.form['chat_id']    
    chat_new= chat.query.filter_by(id=chat_id).first()
    lenghth_hist = len([key for key in chat_new.input.keys()])-1
    print(lenghth_hist)
    chat_output = chat_new.output[str(lenghth_hist)]
    return jsonify({'chat_box': chat_output, })


@app.route('/tasks', methods=['GET'])
def get_all_tasks():
    return jsonify(tasks)

@app.route('/get_tasks', methods=['POST'])
def get_task_status():
    task_id = list(tasks.keys())[len(list(tasks.keys()))-1]
    print(task_id)
    if task_id in tasks:
        task_status = tasks[task_id]
        print(task_status)
        if task_status == "Completed":
            status = 1
        else: 
            status = 0
        return jsonify({"result": status})
    else:
        return jsonify({"result": "not_found", "error": "Task ID not found"})

# http://localhost:5000/tasks

# os.system('taskkill /f /im ngrok.exe')  # Kill any existing ngrok processes
ngrok.set_auth_token("Ngrock Token")  # Set your ngrok auth token here
public_url = ngrok.connect(5000)
print(f" * Ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")

if __name__ == '__main__':
    app.run(debug=True)
    os.system('taskkill /f /im ngrok.exe')

