FROM python:3.13-slim as builder

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем UV и другие необходимые инструменты
RUN pip install uv

# Копируем файлы для установки зависимостей
COPY pyproject.toml .

# Создаем и активируем виртуальное окружение с uv
ENV PATH="/app/.venv/bin:$PATH"

# Устанавливаем зависимости с помощью uv из pyproject.toml
RUN uv sync

FROM python:3.13-slim as runtime

WORKDIR /app

# Копируем виртуальное окружение из этапа сборки
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Копируем код приложения

COPY pyproject.toml .

# Устанавливаем psycopg2 зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Непривилегированный пользователь для повышения безопасности
RUN useradd -m appuser
USER appuser

# Настройка переменных окружения
ENV PYTHONPATH=/app
ENV PORT=8000

# Необходимо добавить healthcheck для корректной работы в k8s
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/ || exit 1

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
# Запуск с использованием uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Порт, который слушает приложение
EXPOSE 8000