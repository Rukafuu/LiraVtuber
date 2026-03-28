from google import genai
from src.providers.google_provider import GoogleProvider

try:
    p = GoogleProvider()
    print("Uploading file...")
    uploaded_file = p.cliente.files.upload(file="src/config/prompt.json")
    print("Uploaded file uri:", uploaded_file.uri)
    print("Uploaded file mime:", uploaded_file.mime_type)
    
    # Try creating a part
    part = genai.types.Part.from_uri(uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
    print("Part:", part)
    print("Success")
except Exception as e:
    print(e)
