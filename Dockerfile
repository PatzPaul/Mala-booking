FROM ubuntu:20.04

# Envs
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.9 \
    python3.9-dev \
    python3-pip \
    && rm -rf /var/lib/lists/*


COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000 

CMD [ "python3", "-m","uvicorn", "app:main:app","--host", "0.0.0.0", "--port", "8000" ]

