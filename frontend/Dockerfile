# Use Node image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install frontend dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy all files
COPY . .

# Expose Vite port
EXPOSE 5173

# Start Vite dev server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
