Fork this repo on [Github](https://github.com/embedchain/embedchain) to create your own assistant for your Slack workspace.

If you run into problems with forking, please refer to [github docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) for forking a repo.

We will work from the `examples/slack_assistant` folder so change your current working directory by running the command - `cd <your_forked_repo>/examples/slack_assistant`

# Developement

1. Create a workspace on Slack if you don’t have one already by clicking [here](https://slack.com/intl/en-in/).
2. Create a new App on your Slack account by going [here](https://api.slack.com/apps).
3. Select `From Scratch`, then enter the App Name and select your workspace.
4. Navigate to `OAuth & Permissions` tab from the left sidebar and go to the `scopes` section. Add the following scopes under `User Token Scopes`:
```
channels:history
search:read
```
5. Click on the `Install to Workspace` button under `OAuth Tokens for Your Workspace` section in the same page and install the app in your slack workspace.
6. After installing the app you will see the `User OAuth Token`, save that token as you will need to configure it as `SLACK_USER_TOKEN` for this demo.
7. Navigate to `api` folder in this directory and set your `OPENAI_API_KEY` and `SLACK_USER_TOKEN` in `.env.example` file. Then rename the `.env.example` file to `.env`.
8. Now to run the app locally, simply run `ec start` from the `slack_assistant` folder to see the full-stack app running on [http://localhost:3000/](http://localhost:3000/).

---
**NOTE**

When using the add functionality with the full-stack app, make sure to provide the channel name as `in:random` or `in:general` to add all the messages with replies from the respective channels. All other values will function similar to search queries in slack workspace.

---