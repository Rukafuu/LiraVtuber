import subprocess
import sys

requirements = [
    "faster-whisper>=1.0.0",
    "azure-cognitiveservices-speech==1.48.2",
    "pyvts==0.3.3",
    "edge-tts==7.2.8",
    "google-cloud-texttospeech==2.34.0",
    "google-cloud-storage>=2.19.0",
    "google-genai>=1.68.0",
    "groq==1.0.0",
    "openai>=1.111.0",
    "keyboard==0.13.5",
    "numpy>=2.2.6",
    "pygame>=2.6.1",
    "python-dotenv==1.2.1",
    "sounddevice==0.5.5",
    "tavily-python==0.7.23",
    "mss==9.0.1",
    "Pillow==10.4.0",
    "psutil>=5.9.0",
    "chromadb>=0.4.0",
    "networkx>=3.0",
    "sentence-transformers>=2.2.0",
    "scikit-learn>=1.0",
    "youtube-transcript-api>=0.6.0",
    "pytest>=8.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "websockets>=12.0"
]

failed = []
success = []

for req in requirements:
    print(f"Installing {req}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req])
        success.append(req)
    except subprocess.CalledProcessError:
        print(f"Failed to install {req}")
        failed.append(req)

print("\n--- Summary ---")
print(f"Success: {len(success)}")
print(f"Failed: {len(failed)}")
for f in failed:
    print(f" - {f}")

if "pygame>=2.6.1" in failed:
    print("\nTrying pygame-ce instead...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pygame-ce"])
        print("pygame-ce installed successfully")
    except subprocess.CalledProcessError:
        print("Failed to install pygame-ce")
