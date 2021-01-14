FROM python:3.8-slim
ARG version

RUN pip install stackmanager==$version

CMD ["stackmanager"]
