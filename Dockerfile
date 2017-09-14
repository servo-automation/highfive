FROM python:2.7.13-alpine3.6

MAINTAINER Ravi Shankar <wafflespeanut@gmail.com>

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN apk update
RUN apk add --no-cache build-base postgresql-dev
RUN pip install --no-cache-dir -r requirements.txt
RUN rm requirements.txt && apk del build-base

COPY cgi-bin/ ./

ENV PORT 8000
ENTRYPOINT ["python", "./serve.py"]
