# Match the published Playwright Python/browser image versions.
ARG PLAYWRIGHT_VERSION=1.61.0
FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble
USER root
ARG PLAYWRIGHT_VERSION=1.61.0
WORKDIR /opt/testwins
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY pyproject.toml README.md LICENSE THIRD_PARTY.md ./
COPY testwins ./testwins
RUN python -m pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}" '.[live]' \
    && python -c "import importlib.metadata as m; assert m.version('playwright') == '${PLAYWRIGHT_VERSION}'" \
    && mkdir -p /work /artifacts && chown -R 1000:1000 /work /artifacts
WORKDIR /work
USER 1000:1000
EXPOSE 9067
ENTRYPOINT ["python", "-m", "testwins", "watch"]
