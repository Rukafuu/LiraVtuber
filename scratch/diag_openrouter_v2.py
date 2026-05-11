
import os
import requests
import base64
import json
from dotenv import load_dotenv

load_dotenv()

or_key = os.getenv("OPENROUTER_API_KEY")
api_url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {or_key}",
    "Content-Type": "application/json"
}
payload = {
    "model": "sourceful/riverflow-v2-fast",
    "messages": [{"role": "user", "content": "a cute pink haired kitsune girl, anime style"}],
    "modalities": ["image"]
}

print("Enviando requisição (Formato Chat + Image Modality)...")
response = requests.post(api_url, headers=headers, json=payload, timeout=60)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    content = data['choices'][0]['message'].get('content', '')
    if "base64," in content:
        print("✅ Imagem recebida em Base64!")
        b64_data = content.split("base64,")[1]
        with open("test_openrouter_new.png", "wb") as f:
            f.write(base64.b64decode(b64_data))
        print("💾 Salva em: test_openrouter_new.png")
    else:
        print("❌ Resposta sem imagem no conteúdo.")
        print(f"DEBUG: {content[:100]}...")
else:
    print(f"❌ Erro: {response.text}")
