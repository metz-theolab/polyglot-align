# Image du front : construit avec Vite, servi par nginx, qui renvoie /api au
# backend (BACKEND_URL). Voir decisions-app.md, « Docker ».
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# modèle de configuration : nginx y remplace ${BACKEND_URL} au démarrage
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000
EXPOSE 80
