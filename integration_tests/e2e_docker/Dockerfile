ARG BASE_VERSION
FROM python:$BASE_VERSION

RUN apt-get update && apt-get install -y gdb \
    && rm -rf /var/lib/apt/lists/*

COPY inferior-simple.py /inferior-simple.py

CMD ["python", "/inferior-simple.py"]
