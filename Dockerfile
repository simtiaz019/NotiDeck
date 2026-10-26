FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS wheel
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY --from=frontend /build/src/notideck/static/ ./src/notideck/static/
RUN pip wheel --no-cache-dir --no-deps . -w /wheels

FROM python:3.12-slim AS runtime
RUN groupadd --gid 10001 notideck && useradd --uid 10001 --gid 10001 --create-home notideck \
    && mkdir /data && chown notideck:notideck /data && chmod 700 /data
COPY --from=wheel /wheels /wheels
RUN pip install --no-cache-dir --upgrade 'pip>=26.2.2' \
    && for wheel in /wheels/notideck-*.whl; do pip install --no-cache-dir "${wheel}[postgres,mysql]"; done \
    && rm -rf /wheels
USER notideck
ENV NOTIDECK_CONFIG_DIR=/data NOTIDECK_DATA_DIR=/data PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)"]
ENTRYPOINT ["notideck"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
