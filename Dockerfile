FROM public.ecr.aws/docker/library/python:3.10-slim
ARG version

RUN apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install stackmanager==$version

CMD ["stackmanager"]
