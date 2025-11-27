FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]