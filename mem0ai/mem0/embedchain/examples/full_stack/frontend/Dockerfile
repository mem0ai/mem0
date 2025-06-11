FROM node:18-slim AS frontend

WORKDIR /usr/src/app/frontend
COPY package.json .
COPY package-lock.json .
RUN npm install

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
