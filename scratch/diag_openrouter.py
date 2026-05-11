
import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

or_key = os.getenv("OPENROUTER_API_KEY")
print(f"Chave encontrada: {or_key[:10]}...")

api_url = "https://openrouter.ai/api/v1/images/generations"
headers = {
    "Authorization": f"Bearer {or_key}",
    "Content-Type": "application/json"
}
payload = {
    "model": "sourceful/riverflow-v2-fast",
    "prompt": "a cute white haired kitsune girl, anime style",
    "response_format": "b64_json"
}

print("Enviando requisição para OpenRouter...")
response = requests.post(api_url, headers=headers, json=payload, timeout=60)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ Sucesso!")
    data = response.json()
    print(f"Tamanho dos dados: {len(str(data))}")
else:
    print(f"❌ Erro: {response.text}")
