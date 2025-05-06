# FROM python:3.9
FROM ubuntu:20.04

# WORKDIR /

RUN apt-get update && apt-get install -y python3.9 python3.9-dev

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# COPY . /

EXPOSE 8000 

CMD [ "fastapi", "run", "app/main.py", "--port", "8000" ]



# COPY . .
# RUN pip install -r requirements.txt
# CMD ["python]