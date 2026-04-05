FROM python:3.13

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app


CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]