FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies needed for node-gyp if necessary
RUN apk add --no-cache libc6-compat

# Copy package manifests
COPY apps/web/package.json ./

# Install node dependencies
RUN npm install

# Copy source code
COPY apps/web ./

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "dev"]
