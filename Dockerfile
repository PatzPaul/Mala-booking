FROM python:3.10-slim


WORKDIR /app



COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN find . -type f -name "*.py" | sort

EXPOSE 8000 

# CMD [ "python3", "-m","uvicorn", "main:app","--host", "0.0.0.0", "--port", "8000" ]
CMD ["sh", "-c", "if [ -f app/main.py ]; then python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000; elif [ -f main.py ]; then python3 -m uvicorn main:app --host 0.0.0.0 --port 8000; elif [ -f api/main.py ]; then python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000; else echo 'Could not find FastAPI application entry point' && exit 1; fi"]


