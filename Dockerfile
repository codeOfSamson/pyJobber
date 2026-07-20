FROM --platform=linux/amd64 mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends xvfb && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python3 -m patchright install chromium

COPY . .

ENV ENV=production

CMD ["sh", "-c", "xvfb-run --auto-servernum --server-args='-screen 0 1280x800x24' python3 main.py"]
