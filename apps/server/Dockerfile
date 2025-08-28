FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files for dependency resolution
COPY pyproject.toml uv.lock ./

# Install Python dependencies to system location
RUN uv sync --frozen

# Copy project
COPY . .

# Expose port
EXPOSE 7175

# Run the application
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:7175"]
