from google import genai

try:
    part = genai.types.Part.from_uri(file_uri="https://generativelanguage.googleapis.com/v1beta/files/g44bybvyxpy7", mime_type="application/json")
    print("Part created successfully:", part)
except Exception as e:
    print(e)
