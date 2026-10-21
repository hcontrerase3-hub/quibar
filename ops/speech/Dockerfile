FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /voice
COPY ops/speech/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
 && useradd -u 10001 quibar-voice && mkdir /models && chown quibar-voice /models
COPY ops/speech/server.py .
USER 10001
CMD ["python", "server.py"]
