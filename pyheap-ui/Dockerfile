FROM python:3.10.7-alpine3.16

RUN pip install flask==2.2.2

RUN mkdir /pyheap && mkdir /pyheap-workdir
RUN addgroup -S pyheap \
    && adduser -S pyheap -G pyheap

COPY ./src /pyheap

USER pyheap

EXPOSE 5000

ENV FLASK_SERVER_NAME=0.0.0.0
ENV PYTHONPATH=/pyheap
WORKDIR /pyheap-workdir
ENTRYPOINT ["python3", "-m", "ui", "--file"]
CMD []
