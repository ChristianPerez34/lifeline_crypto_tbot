FROM python:3.8.12-buster

ENV PYTHONUNBUFFERED=1
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
ENV PYTHONPATH='/lifeline_crypto_tbot'

WORKDIR /lifeline_crypto_tbot
RUN apt-get update && apt-get -y upgrade && apt-get -y install build-essential libssl-dev libffi-dev python3-dev \
    cargo libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir --upgrade -r requirements.txt
COPY . /lifeline_crypto_tbot
