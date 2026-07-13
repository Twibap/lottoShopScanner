FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY src/ ./src/

ENTRYPOINT ["python", "src/fetch_winning_shops.py"]
CMD ["--help"]
