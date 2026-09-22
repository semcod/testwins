FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
# Set a reviewed commit SHA for repeatable deployments. A floating ref must be an operator choice.
ARG PLANFILE_REF=main
RUN python -m pip install --no-cache-dir "PyYAML==6.0.3" "git+https://github.com/semcod/planfile.git@${PLANFILE_REF}" \
    && python -c "from planfile import Planfile; from planfile.contracts import TicketProposalV1; assert hasattr(Planfile, 'create_ticket_deduplicated')"
WORKDIR /opt/testwins
COPY testwins ./testwins
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["python", "-m", "testwins"]
