ARG PLAYWRIGHT_VERSION=1.61.0
FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git xvfb xauth x11-utils python3-tk x11-apps xdotool wmctrl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/testwins
COPY pyproject.toml requirements.txt README.md LICENSE THIRD_PARTY.md ./
COPY testwins/ ./testwins/
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir '.[desktop,cv,terminal]'
# Public verification API may be newer than the PyPI release. Pin a reviewed SHA for release builds.
ARG TESTQL_REF=main
RUN python -m pip install --no-cache-dir "git+https://github.com/autogrammar/testql.git@${TESTQL_REF}" \
    && python -c 'from testql.verification import VerificationRequest,run_verification'
COPY docker/worker-entrypoint.sh /usr/local/bin/testwins-worker
RUN chmod 755 /usr/local/bin/testwins-worker
ENV HOME=/tmp/home PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
USER 1000:1000
ENTRYPOINT ["/usr/local/bin/testwins-worker"]
