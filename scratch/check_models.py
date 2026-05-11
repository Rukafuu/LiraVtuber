import requests
import json

def list_models():
    url = "https://openrouter.ai/api/v1/models"
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('data', [])
        print(f"Total models: {len(models)}")
        for m in models:
            if 'free' in m['id'].lower():
                print(f"FREE MODEL: {m['id']}")
    else:
        print(f"Error: {response.status_code}")

if __name__ == "__main__":
    list_models()
