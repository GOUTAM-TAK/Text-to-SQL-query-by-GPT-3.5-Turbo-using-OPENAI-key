# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file into the image
COPY requirements.txt requirements.txt

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the image
COPY . .

# Set environment variables
# If you're using a .env file, this should be handled in Docker Compose or at runtime
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

# Expose port 5000
EXPOSE 5000

# Run the application with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
