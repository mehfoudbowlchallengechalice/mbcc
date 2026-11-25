FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home mbcc

COPY backend/__init__.py backend/server.py backend/sheets_adapter.py backend/groups.py /app/backend/
COPY cloudrun/gunicorn.conf.py /app/cloudrun/gunicorn.conf.py
COPY ios/MBCC/demo.json /app/ios/MBCC/demo.json

USER mbcc
CMD ["gunicorn", "--config", "cloudrun/gunicorn.conf.py", "backend.server:application"]

