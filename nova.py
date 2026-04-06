import os
from openai import OpenAI
from core.memory import Memory

# 1. Point directly to your local LM Studio server
client = OpenAI(
    base_url="http://localhost:1234/v1", 
    api_key="lm-studio" # Required parameter, but the value is ignored locally
)

# Initialize the memory organ
mem = Memory()

def get_nova_response(user_input):
    # 2. Retrieve Context from Database
    # Using the exact keys we just verified in test_memory.py
    user_name = mem.load("user_name").get("name", "Unknown")
    current_goal = mem.load("goal").get("goal", "Unknown")
    
    # 3. Build the Identity
    system_content = (
        "You are Nova, a precision execution AI. "
        f"User Name: {user_name}. "
        f"Current Goal: {current_goal}. "
        "Be concise, technical, and execution-focused. Do not use fluff."
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input}
    ]

    # 4. Call Local Llama 8B via LM Studio
    try:
        response = client.chat.completions.create(
            model="local-model", # LM Studio routes this to whatever model is loaded
            messages=messages,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        
        # 5. Save interaction (Learning)
        mem.save("last_interaction", {"user": user_input, "nova": answer})
        
        return answer

    except Exception as e:
        return f"[ERROR] Connection failed. Is the LM Studio local server running? Details: {str(e)}"

def main():
    print("--- Nova Online (Local Engine + Memory Active) ---")
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                break
            
            response = get_nova_response(user_input)
            print(f"\nNova: {response}")
            
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()