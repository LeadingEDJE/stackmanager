FROM python:3.8-slim
ARG version

RUN apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install stackmanager==$version

CMD ["stackmanager"]
