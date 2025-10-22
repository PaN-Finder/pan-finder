FROM node:20-alpine AS build
WORKDIR /app

ARG API
ENV REACT_APP_API=$API

ARG PAN_FINDER_API
ENV REACT_APP_PAN_FINDER_API=$PAN_FINDER_API

# Turnstile configuration
ARG ENABLE_TURNSTILE=true
ENV REACT_APP_ENABLE_TURNSTILE=$ENABLE_TURNSTILE

# Turnstile site key (not sensitive, can be public)
ARG TURNSTILE_SITE_KEY
ENV REACT_APP_TURNSTILE_SITE_KEY=$TURNSTILE_SITE_KEY

COPY package.json ./
COPY package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build

FROM nginx:alpine
COPY nginx-spa.conf /etc/nginx/nginx.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
