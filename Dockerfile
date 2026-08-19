# Agent Reliability Engine — container image.
#
# Sandbox layer L3 (§7.9) is enforced *outside* this file, by how the container is run:
# `docker compose run offline` starts it with `network_mode: none`, which is an OS-level
# deny-all that no Python-level guard can be talked out of. The in-process egress guard in
# runner/sandbox.py is the fallback for running on the host.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    ARE_IN_CONTAINER=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY are/ ./are/
COPY frozen/ ./frozen/
COPY tests/ ./tests/

# Runs never write outside these two directories.
RUN mkdir -p /app/runs /app/pool && useradd -m -u 10001 are \
    && chown -R are:are /app/runs /app/pool
USER are

ENTRYPOINT ["python", "-m", "are.cli"]
CMD ["selftest"]
