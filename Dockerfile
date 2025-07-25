FROM python:3.12.3-slim


RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libpq-dev \
    ffmpeg \
    mediainfo \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


COPY requirements.txt .


RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


COPY . .


CMD ["python", "app.py"]