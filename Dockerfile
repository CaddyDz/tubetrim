FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JS runtime to solve YouTube signature challenges;
# without one, many formats 403 (see yt-dlp wiki: EJS)
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /srv

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY pyproject.toml ./
COPY app ./app
COPY static ./static
COPY tests ./tests

ENV DATA_DIR=/srv/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
