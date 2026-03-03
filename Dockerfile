FROM oven/bun:latest

# Set work directory
WORKDIR /app

# Copy package files
COPY package.json bun.lock* ./

# Install dependencies
RUN bun install --frozen-lockfile

# Copy project
COPY . .

# Build the application
RUN bun run build

# Expose port
EXPOSE 8008

# Run the application
CMD ["bun", "run", "preview", "--host", "0.0.0.0", "--port", "8008"]
