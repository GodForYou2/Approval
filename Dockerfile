# ddddocr အတွက် အတည်ငြိမ်ဆုံးဖြစ်သော Python 3.10-slim ကို သုံးပါ
FROM python:3.10-slim

WORKDIR /app

# ddddocr နှင့် OpenCV အတွက် လိုအပ်သော Linux dependencies များ သွင်းပေးခြင်း
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Pip ကို upgrade လုပ်ပြီးမှ dependencies များကို သွင်းခြင်း
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# မိမိ Bot ရဲ့ Main File အမည်ကို ရေးပါ
CMD ["python", "bb.py"]
