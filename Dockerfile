# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port your Flask app will run on
# Render will expose this port to the internet
EXPOSE 10000 # Render typically uses port 10000 for web services

# Define environment variable for production
ENV FLASK_ENV=production

# Command to run the Flask application using Gunicorn
# -w: number of worker processes (e.g., 2-4 depending on CPU cores)
# -b: bind to all network interfaces on the exposed port
# app:app: refers to the 'app' instance within 'app.py'
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:10000", "app:app"]
