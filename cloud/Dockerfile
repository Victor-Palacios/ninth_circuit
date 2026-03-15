FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY pipeline/ pipeline/
COPY cloud/main.py .
COPY cloud/run_fetch.py .
COPY cloud/run_classify.py .
COPY cloud/run_extract.py .
COPY cloud/entrypoint.py .

ENV PYTHONUNBUFFERED=1
ENV PIPELINE_STEP=all

CMD ["python", "entrypoint.py"]
