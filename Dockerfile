FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg curl tesseract-ocr tesseract-ocr-tur && rm -rf /var/lib/apt/lists/*
RUN T=$(dirname "$(find /usr/share/tesseract-ocr -name tur.traineddata | head -1)") && curl -fsSL -o "$T/tur.traineddata" https://github.com/tesseract-ocr/tessdata_best/raw/main/tur.traineddata
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
