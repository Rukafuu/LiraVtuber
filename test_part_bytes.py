from google import genai

try:
    part = genai.types.Part.from_bytes(data=b"hello", mime_type="image/png")
    print(part)
except Exception as e:
    print(e)
