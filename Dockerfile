FROM python:3.8-alpine
ARG version

RUN pip install stackmanager==$version

CMD ["stackmanager"]
