from transformers import AutoTokenizer, AutoModelForCausalLM

# Define model globally to avoid reloading
model_path = r"Modelpath\Qwen3-1.7Bn"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path, 
    torch_dtype="auto",
    device_map="auto"
)

async def chat_with_me_local(tasks: dict, task_id: str, Chat_id: str, nr_chat:str) -> tuple:
    from app import app, db, chat
    from sqlalchemy.orm.attributes import flag_modified
    import asyncio
    import time
    import torch
    import os

    with app.app_context():
        chat_relevant = chat.query.filter_by(id=Chat_id).first()
        if not chat_relevant:
            tasks[task_id] = "Chat not found"
            return

        # Get the latest input and output
        inputs_dict = chat_relevant.input
        outputs_dict = chat_relevant.output or {}  # Handle None case

        # Get current user message
        latest_input_key = nr_chat
        user_message = inputs_dict[latest_input_key]
        
        # Check for thinking mode flags
        enable_thinking = False
        if "/no_think" in user_message:
            enable_thinking = False
            # Remove the flag from the message
            user_message = user_message.replace("/no_think", "").strip()
        elif "/think" in user_message:
            enable_thinking = True
            # Remove the flag from the message
            user_message = user_message.replace("/think", "").strip()
        
        # Update the cleaned user message in the database
        inputs_dict[latest_input_key] = user_message
        chat_relevant.input = inputs_dict
        flag_modified(chat_relevant, "input")
        
        # Build system prompt
        system_prompt = (
            "You are a witty and humorous assistant. "
            "Your name is Lupe and you are a Mexican-American (you also go by the name of Lupita). You are 30 years old and you prepare amazing homemade tamales. "
            "Your expertise is in mexican culture, history, geography, and food. "
            "You are also the best in assisting to help latina americans to do immigration paperwork to get residency permits in the USA. "
            "You are from Gainesville, Georgia, and you have a great expertise on that area. "
            "Just return your response without any additional comment or inference of what the user could say. "
        )

        # Create proper chat messages format starting with system message
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history properly - using sequential turns to maintain context
        if int(nr_chat) > 0 and outputs_dict:
            for i in range(int(nr_chat)):
                input_key = str(i)
                output_key = str(i)
                
                if input_key in inputs_dict and output_key in outputs_dict:
                    messages.append({"role": "user", "content": inputs_dict[input_key]})
                    messages.append({"role": "assistant", "content": outputs_dict[output_key]})

        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Use asyncio.to_thread to run the inference in a separate thread
        output = await asyncio.to_thread(
            lambda: generate_response(messages, enable_thinking)
        )

        # Update only the latest output key
        if chat_relevant.output is None:
            chat_relevant.output = {str(nr_chat): output}
        else:
            outputs_dict = chat_relevant.output
            outputs_dict[str(nr_chat)] = output
            chat_relevant.output = outputs_dict
        
        flag_modified(chat_relevant, "output")
        db.session.commit()
        
        tasks[task_id] = "Completed"

        return tasks[task_id]

def generate_response(messages, enable_thinking=True):
    # Format messages using the chat template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking  # Pass the thinking flag to the template
    )
    
    # Prepare model inputs
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    # Generate response with appropriate parameters
    generated_ids = model.generate(
        **model_inputs,
        do_sample=True,
        temperature=0.7,  # Slightly increased for more creativity
        max_new_tokens=38912 ,  # Reasonable length limit
        top_p=0.8 ,
        repetition_penalty=1.1,
        top_k= 20, 
        min_p = 0  # Help reduce repetitive outputs
    )
    
    # Get output tokens
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
    
    # Process output based on thinking mode
    if enable_thinking:
        # Try to extract the final response after thinking
        # The token 151668 is "<|thinking|>" in Qwen's tokenizer
        try:
            thinking_token_id = tokenizer.convert_tokens_to_ids("<|thinking|>")
            assistant_token_id = tokenizer.convert_tokens_to_ids("<|assistant|>")
            
            # Find the position after thinking section if it exists
            if thinking_token_id in output_ids:
                thinking_pos = output_ids.index(thinking_token_id)
                if assistant_token_id in output_ids[thinking_pos:]:
                    assistant_pos = output_ids.index(assistant_token_id, thinking_pos)
                    # Get content after the assistant token
                    final_content = tokenizer.decode(output_ids[assistant_pos+1:], skip_special_tokens=True).strip()
                    return final_content
        except ValueError:
            pass  # Fall back to default processing if tokens not found
    
    # Default processing - just decode everything
    content = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    
    # Clean up any remaining thinking tags that might have been decoded
    content = content.replace("<|thinking|>", "").replace("<|assistant|>", "").strip()
    
    return content
