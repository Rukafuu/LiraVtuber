from src.providers.google_provider import GoogleProvider
from google import genai

try:
    p = GoogleProvider()
    print("Testing generate_content with Part.from_bytes")
    
    with open("src/config/prompt.json", "rb") as f:
        img_bytes = f.read()  # actually json but let's test bytes
        
    part = genai.types.Part.from_bytes(data=b"dummyimagebytes", mime_type="image/png")
    
    res = p._chamar_api("gemini-3.1-pro-preview", [{"role": "user", "content": "What is this?"}], image_b64=None)
    print("Clean response without image:", res.choices[0].message.content)
    
    import base64
    b64 = base64.b64encode(b"dummyimagebytes").decode("utf-8")
    res2 = p._chamar_api("gemini-3.1-pro-preview", [{"role": "user", "content": "What is this?"}], image_b64=b64)
    print("Response with image:", res2.choices[0].message.content)
except Exception as e:
    import traceback
    traceback.print_exc()
