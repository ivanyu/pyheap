FROM python:3.10.8-bullseye

RUN apt-get update && apt-get install -y gdb \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

COPY ./ /inferiors/
WORKDIR /inferiors

ENV PATH="/root/.local/bin:$PATH"

RUN poetry install
