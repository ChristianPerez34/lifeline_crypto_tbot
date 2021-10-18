FROM python:3.7
ENV PYTHONUNBUFFERED=1
WORKDIR /lifeline_crypto_tbot

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . /lifeline_crypto_tbot