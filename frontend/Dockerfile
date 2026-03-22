FROM node:20-alpine

# Kafin v6.1.4 - Prompt Quality + Modell-Optimierung
# Aktuelle Features: API Usage Tracking, Prompt Quality v0.4, DeepSeek Modell-Matrix

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
