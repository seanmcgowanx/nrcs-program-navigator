# Backend image for the FastAPI serving layer (nrcs_navigator.serving.app).
#
# Two tools (practice_matcher, program_availability) drive a real headless
# Chromium to scrape JS-rendered NRCS pages, so the image needs Chromium plus
# its system libraries. Playwright's official base image ships all three
# browser engines (Chromium, Firefox, WebKit); we only use Chromium, so instead
# of inheriting that ~4GB image we start from a slim Python base and install
# *only* Chromium with its OS dependencies via `playwright install --with-deps`.
# The Python interpreter (3.10) satisfies the project's >=3.10,<3.13 constraint.
FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install Python dependencies first (exported from poetry.lock) so this layer
# caches until the lock changes. playwright the CLI arrives with this install.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install ONLY the Chromium browser and the apt packages it needs to run. The
# Playwright client version (from requirements.txt) and the browser it pulls
# stay matched because the CLI installs the build it was released with. Clean
# apt lists in the same layer so they do not bloat the image.
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Then the application code and metadata, installed without re-resolving deps.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .

# Render provides $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn nrcs_navigator.serving.app:app --host 0.0.0.0 --port ${PORT}"]
