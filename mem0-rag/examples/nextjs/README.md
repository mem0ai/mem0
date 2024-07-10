Fork this repo on [Github](https://github.com/embedchain/embedchain) to create your own NextJS discord and slack bot powered by Embedchain app.

If you run into problems with forking, please refer to [github docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) for forking a repo.

We will work from the examples/nextjs folder so change your current working directory by running the command - `cd <your_forked_repo>/examples/nextjs`

# Installation

First, lets start by install all the required packages and dependencies.

- Install all the required python packages by running `pip install -r requirements.txt`.

- We will use [Fly.io](https://fly.io/) to deploy our embedchain app and discord/slack bot. Follow the step one to install [Fly.io CLI](https://docs.embedchain.ai/deployment/fly_io#step-1-install-flyctl-command-line)

# Developement

## Embedchain App

First, lets get started by creating an Embedchain app powered with the knowledge of NextJS. We have already created an embedchain app using FastAPI in `ec_app` folder for you. Feel free to ingest data of your choice to power the App.

---
**NOTE**

Create `.env` file in this folder and set your OpenAI API key as shown in `.env.example` file. If you want to use other open-source models, feel free to change the app config in `app.py`. More details for using custom configuration for Embedchain app is [available here](https://docs.embedchain.ai/api-reference/advanced/configuration).

---

Before running the ec commands to develope/deploy the app, open `fly.toml` file and update the `name` variable to something unique. This is important as `fly.io` requires users to provide a globally unique deployment app names.

Now, we need to launch this application with fly.io. You can see your app on [fly.io dashboard](https://fly.io/dashboard). Run the following command to launch your app on fly.io:
```bash
fly launch --no-deploy
```

To run the app in development:

```bash
ec dev  #To run the app in development environment
```

Run `ec deploy` to deploy your app on Fly.io. Once you deploy your app, save the endpoint on which our discord and slack bot will send requests.


## Discord bot

For discord bot, you will need to create the bot on discord developer portal and get the discord bot token and your discord bot name.

While keeping in mind the following note, create the discord bot by following the instructions from our [discord bot docs](https://docs.embedchain.ai/examples/discord_bot) and get discord bot token.

---
**NOTE**

You do not need to set `OPENAI_API_KEY` to run this discord bot. Follow the remaining instructions to create a discord bot app. We recommend you to give the following sets of bot permissions to run the discord bot without errors:

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

Once you have your discord bot token and discord app name. Navigate to `nextjs_discord` folder and create `.env` file and define your discord bot token, discord bot name and endpoint of your embedchain app as shown in `.env.example` file.

To run the app in development:

```bash
python app.py  #To run the app in development environment
```

Before deploying the app, open `fly.toml` file and update the `name` variable to something unique. This is important as `fly.io` requires users to provide a globally unique deployment app names.

Now, we need to launch this application with fly.io. You can see your app on [fly.io dashboard](https://fly.io/dashboard). Run the following command to launch your app on fly.io:
```bash
fly launch --no-deploy
```

Run `ec deploy` to deploy your app on Fly.io. Once you deploy your app, your discord bot will be live!


## Slack bot

For Slack bot, you will need to create the bot on slack developer portal and get the slack bot token and slack app token.

### Setup

- Create a workspace on Slack if you don't have one already by clicking [here](https://slack.com/intl/en-in/).
- Create a new App on your Slack account by going [here](https://api.slack.com/apps).
- Select `From Scratch`, then enter the Bot Name and select your workspace.
- Go to `App Credentials` section on the `Basic Information` tab from the left sidebar, create your app token and save it in your `.env` file as `SLACK_APP_TOKEN`.
- Go to `Socket Mode` tab from the left sidebar and enable the socket mode to listen to slack message from your workspace.
- (Optional) Under the `App Home` tab you can change your App display name and default name.
- Navigate to `Event Subscription` tab, and enable the event subscription so that we can listen to slack events.
- Once you enable the event subscription, you will need to subscribe to bot events to authorize the bot to listen to app mention events of the bot. Do that by tapping on `Add Bot User Event` button and select `app_mention`.
- On the left Sidebar, go to `OAuth and Permissions` and add the following scopes under `Bot Token Scopes`:
```text
app_mentions:read
channels:history
channels:read
chat:write
emoji:read
reactions:write
reactions:read
```
- Now select the option `Install to Workspace` and after it's done, copy the `Bot User OAuth Token` and set it in your `.env` file as `SLACK_BOT_TOKEN`.

Once you have your slack bot token and slack app token. Navigate to `nextjs_slack` folder and create `.env` file and define your slack bot token, slack app token and endpoint of your embedchain app as shown in `.env.example` file.

To run the app in development:

```bash
python app.py  #To run the app in development environment
```

Before deploying the app, open `fly.toml` file and update the `name` variable to something unique. This is important as `fly.io` requires users to provide a globally unique deployment app names.

Now, we need to launch this application with fly.io. You can see your app on [fly.io dashboard](https://fly.io/dashboard). Run the following command to launch your app on fly.io:
```bash
fly launch --no-deploy
```

Run `ec deploy` to deploy your app on Fly.io. Once you deploy your app, your slack bot will be live!
