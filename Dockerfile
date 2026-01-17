FROM python:3.14-slim

WORKDIR /srv/app/demiurg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY config.toml.example .

CMD ["python3", "-m", "api.main", "config.toml.example"]
