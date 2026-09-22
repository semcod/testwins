# Package and browser revision must match. Override both together when upgrading.
ARG PLAYWRIGHT_VERSION=1.61.0
FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble AS engines
USER root
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb fluxbox x11vnc novnc websockify x11-utils git xauth curl ca-certificates gnupg \
      fonts-dejavu-core fonts-liberation fonts-noto-core nodejs npm \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/testwins
COPY requirements.txt pyproject.toml README.md LICENSE THIRD_PARTY.md ./
COPY testwins ./testwins
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps . \
    && mkdir -p /opt/testwins-assets \
    && npm install --prefix /opt/testwins-assets --ignore-scripts --no-audit --no-fund axe-core@4.10.3 \
    && cp /opt/testwins-assets/node_modules/axe-core/axe.min.js /opt/testwins-assets/axe.min.js
ARG TESTQL_REF=main
RUN python -m pip install --no-cache-dir "git+https://github.com/autogrammar/testql.git@${TESTQL_REF}" \
    && python -c "from testql.verification import VerificationRequest,run_verification"
COPY docker/entrypoint.sh /usr/local/bin/testwins-desktop
COPY tools/report_server.py /opt/testwins/report_server.py
RUN chmod 755 /usr/local/bin/testwins-desktop \
    && mkdir -p /work /artifacts && chown -R 1000:1000 /work /artifacts
ENV DISPLAY=:99 HOME=/tmp/testwins-home PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
EXPOSE 6080 8088
USER 1000:1000
ENTRYPOINT ["/usr/local/bin/testwins-desktop"]

FROM engines AS cdp
USER root
# Chrome and Edge packages target Linux amd64. Runtime matrix uses actual brand binaries over CDP.
RUN python -m playwright install chrome msedge \
    && curl --fail --silent --show-error --location \
       https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg \
       --output /usr/share/keyrings/brave-browser-archive-keyring.gpg \
    && curl --fail --silent --show-error --location \
       https://brave-browser-apt-release.s3.brave.com/brave-browser.sources \
       --output /etc/apt/sources.list.d/brave-browser-release.sources \
    && apt-get update && apt-get install -y --no-install-recommends brave-browser \
    && rm -rf /var/lib/apt/lists/*
USER 1000:1000
