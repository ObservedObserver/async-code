# Use the official Node.js runtime as the base image
FROM node:20.9.0-alpine

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies that might be needed
RUN apk add --no-cache \
    bash \
    git \
    curl \
    vim

# Install claude-code globally
RUN npm install -g @anthropic-ai/claude-code

# Copy package files first (for better Docker layer caching)
COPY async-code-web/package*.json ./

# Install Node.js dependencies
RUN npm install

# Copy the rest of the application code
COPY async-code-web/ .

# Copy the setup script
COPY setup.sh ./setup.sh

# Make the setup script executable
RUN chmod +x ./setup.sh

# Expose the port that the app runs on (adjust if needed)
EXPOSE 3000

# Set the default command to run setup.sh
CMD ["/bin/bash", "./setup.sh"]
