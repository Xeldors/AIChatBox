

async def chat_with_me(tasks: dict, task_id: str, model_GPT: str, GPT_API: str, Chat_id: str) -> tuple:
    from app import app, db, chat, api_status
    import openai

    import asyncio
    import time
    with app.app_context():
        chat_relevant = chat.query.filter_by(id=Chat_id).first()
        chat = chat_relevant.input
        client = openai.AsyncOpenAI(api_key=GPT_API)
        chatuser = {"role": "user","content": chat}        
        messages = [
            {"role": "system", "content": (
                "You are a witty and humorous assistant. "
                "Your expertise is in mexican culture, history, geography, and food. "
                "You are also the best in assisting to help latina americans to do immigatuon paperwork to get residency permits in the USA. "
            )},
            chatuser
        ]
        response = await client.chat.completions.create(
            model=model_GPT,
            messages=messages,
            temperature=0.5,
            presence_penalty=0.5,
            frequency_penalty=0.1,
            top_p=0.9
        )

        prompt_tokens_p = 0.15 / 1_000_000,
        completion_tokens_p = 0.6 / 1_000_000

        output = response.choices[0].message.content.strip()
        chat_relevant.output = output
        try:
            api_status_relevant = api_status.query.filter_by(provider='openai', model=model_GPT, key=GPT_API).first()
            if api_status_relevant:
                api_status_relevant.usage += float(response.usage.prompt_tokens) * prompt_tokens_p[0] + float(response.usage.completion_tokens) * completion_tokens_p[0]
                api_status_relevant.api_status = 0
            else:
                # Handle case where api_status_relevant is None, maybe log a warning
                tasks["DB Warning"] = f"No api_status found for provider='openai', model={model_GPT}, key=***"
        except Exception as e:
            tasks["DB Error"] = f"Error updating usage in DB: {e}"
        db.session.commit()
        
        tasks[task_id] = f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"

        return tasks[task_id]
