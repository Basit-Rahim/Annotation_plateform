FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    python -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'))['project'];print('\n'.join(d['dependencies']+d['optional-dependencies']['dev']))" > /tmp/req.txt && \
    pip install -r /tmp/req.txt

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
