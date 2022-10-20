FROM python:3.10.7-alpine3.16

RUN mkdir /pyheap \
    && mkdir /pyheap-workdir
RUN addgroup -S pyheap \
    && adduser -S pyheap -G pyheap

ADD requirements.txt /pyheap
RUN pip3 install -r /pyheap/requirements.txt

COPY ./src /pyheap

USER pyheap

EXPOSE 5000

ENV FLASK_SERVER_NAME=0.0.0.0
ENV PYTHONPATH=/pyheap
ENV FLASK_DEBUG=false
WORKDIR /pyheap-workdir
ENTRYPOINT ["python3", "-m", "pyheap_ui", "--file"]
CMD []
