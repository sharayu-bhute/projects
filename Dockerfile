FROM python:3.10

# set working directory
WORKDIR /app

# copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the app
COPY . .

# expose port
EXPOSE 8000

# run server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
