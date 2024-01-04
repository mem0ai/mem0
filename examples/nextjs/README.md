Fork this repo on [Github](https://github.com/embedchain/embedchain) to create your own NextJS discord and slack bot powered by Embedchain app.

If you run into problems with forking, please refer to [github docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) for forking a repo.

We will work from the examples/nextjs folder so change your current working directory by running the command - `cd <your_forked_repo>/examples/nextjs`

### Installation

First, lets start by install all the required packages and dependencies.

- Install all the required python packages by running `pip install -r requirements.txt`.

- We will use [Fly.io](https://fly.io/) to deploy our embedchain app and discord/slack bot. Follow the step one to install [Fly.io CLI](https://docs.embedchain.ai/deployment/fly_io#step-1-install-flyctl-command-line)

### Developement

1. We have already created an embedchain app using FastAPI in `ec_app` folder.

---
**NOTE**

Create `.env` file in this folder and set your OpenAI API key as shown in `.env.example` file.
---

To run the app in development:

```bash
ec dev  #To run the app in development mode
```

Run `ec deploy` to deploy your app on Fly.io. Once you deploy your app, save the endpoint on which our discord and slack bot will send requests.

2. For discord bot, you will need to create the bot on discord developer portal and get the discord bot token and your discord bot name.

Follow the instructions from our [discord bot docs](https://docs.embedchain.ai/examples/discord_bot).

---
**NOTE**

You do not need to set `OPENAI_API_KEY` to run this discord bot. Follow the remaining steps to create a discord bot app. We recommend you to give the following sets of bot permissions to run the discord bot without errors:

```
(General Permissions)
Read Message/View Channels

(Text Permissions)
Send Messages
Create Public Thread
Create Private Thread
Send Messages in Thread
Manage Threads
Embed Links
Read Message History
```
---

Once you have your discord bot token and discord app name. Create `.env` file and define your discord bot token, discord bot name and endpoint of your embedchain app as shown in `.env.example` file.

To run the app in development:

```bash
python app.py  #To run the app in development mode
```

Run `ec deploy` to deploy your app on Fly.io. Once you deploy your app, your discord bot will be live!

3. 

