FROM langchain/langgraph-api:0.12.6-py3.12

USER root

# -- GDAL system dependencies (single layer) --
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates libgdal-dev libgeos-dev libproj-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV GDAL_CONFIG=/usr/bin/gdal-config \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal

# -- Install 3rd-party deps from pre-exported requirements (no lock resolution) --
COPY dist/requirements.txt /tmp/dist/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    PYTHONDONTWRITEBYTECODE=1 uv pip install --system \
    -c /api/constraints.txt \
    -r /tmp/dist/requirements.txt

# -- Install project wheels (no-deps: everything already installed above) --
COPY dist/*.whl /tmp/dist/
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist

# -- LangGraph entry points (module paths, not file paths) --
ENV LANGGRAPH_HTTP='{"app": "api.main:app"}'
ENV LANGSERVE_GRAPHS='{"agent": "agent.graph:graph", "db_agent": "db_agent_v2.graph:graph", "computer": "computer.graph:graph"}'


# -- Ensure user deps didn't inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN --mount=type=cache,target=/root/.cache/uv \
    PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-deps -e /api

WORKDIR /app
# -- Strip build tooling from final image --
RUN pip uninstall -y pip setuptools wheel 2>/dev/null; \
    rm -rf /usr/local/lib/python*/site-packages/{pip,setuptools,wheel}* \
           /usr/lib/python*/site-packages/{pip,setuptools,wheel}*; \
    find /usr/local/bin /usr/bin -name "pip*" -delete 2>/dev/null; \
    uv pip uninstall --system pip setuptools wheel 2>/dev/null; \
    rm -f /usr/bin/uv /usr/bin/uvx || true