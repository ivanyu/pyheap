FROM python:3.10.8-bullseye

RUN groupadd -g 10042 testgroup && useradd --uid 10123 testuser -g testgroup --create-home

RUN apt-get update && apt-get install -y gdb \
    && rm -rf /var/lib/apt/lists/*

USER testuser

RUN curl -sSL https://install.python-poetry.org | python3 -

COPY ./ /inferiors/
WORKDIR /inferiors

ENV PATH="/home/testuser/.local/bin:$PATH"

RUN poetry install
