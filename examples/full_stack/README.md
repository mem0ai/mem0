# embedchain-ui

embedchain-ui is a responsive full stack web application made using Next.js and Flask and powered by [embedchain](https://github.com/embedchain/embedchain) python package. It provides an easy-to-use user interface for running the embedchain python package.

# 🔧 Setup & Installation

## 🐳 Docker Setup

- To setup embedchain-ui using docker, run the following commands in your terminal after cloning the repository.

```bash
cd embedchain-ui
docker-compose build
```

📝 Note: The build command might take a while to install all the packages depending on your system resources.

- To run the docker application, use the following command.

```bash
docker-compose up
```

📝 Note: If a new version of the `embedchain` package is released, open Docker Desktop, go to the `embedchain_backend` container inside the `embedchain_ui` container, and run the following command in its terminal. After that restart your server to see the changes.

```bash
pip install embedchain --upgrade
```

## 🛠️ Manual Setup

- To setup embedchain-ui manually, follow the next steps after cloning the repository.

### 🧩 Setup Backend

- Make sure that you have the following installed: Python 3 and virtualenv, and you are inside the `backend` folder.

```bash
cd embedchain-ui/backend
```

- Create and activate your virtual environment as follows.

```bash
# For Linux Users
virtualenv -p $(which python3) pyenv
source pyenv/bin/activate

# For Windows users
virtualenv pyenv
.\pyenv\Scripts\activate
```

- Install all the required packages using this command.

```bash
pip install -r requirements.txt
```

📝 Note: Installing the packages might take a while, please wait for the installation to complete.

- Run the backend on localhost port 8000, using this command.

```bash
python server.py
```

📝 Note: If a new version of the `embedchain` package is released, activate your virtual environment and run the following command. After that restart your server to see the changes.

```bash
pip install embedchain --upgrade
```

### 🎨 Setup Frontend

- Make sure that you have the following installed: Node.js, and you are inside the `frontend` folder.

```bash
cd embedchain-ui/frontend
```

- Install all the packages and run the build command.

```bash
npm install
npm run build
```

- Run the frontend on localhost port 3000, using this command.

```bash
npm start
```

# 🚀 Usage Instructions

- Go to [http://localhost:3000/](http://localhost:3000/) in your browser to view the dashboard.
- Add your `OpenAI API key` 🔑 in the Settings.
- Create a new bot and you'll be navigated to its page.
- Here you can add your data sources and then chat with the bot.

🎉 Happy Chatting! 🎉
