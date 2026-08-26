FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask

RUN useradd -m -s /bin/bash sandbox

USER sandbox
WORKDIR /home/sandbox

COPY --chown=sandbox:sandbox sandbox_run.py /home/sandbox/sandbox_run.py

ENTRYPOINT ["python3", "/home/sandbox/sandbox_run.py"]