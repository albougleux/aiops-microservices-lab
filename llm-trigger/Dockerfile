FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code into the image
COPY . .

EXPOSE 5000

CMD ["python", "-u", "analyzer.py"]