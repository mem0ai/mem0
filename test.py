from embedchain import App

# Create a bot instance
elon_bot = App()

# Embed online resources
h = elon_bot.add("https://en.wikipedia.org/wiki/Elon_Musk")
print(h)
h = elon_bot.add("https://tesla.com/elon-musk")
print(h)
h = elon_bot.add("https://www.youtube.com/watch?v=MxZpaJK74Y4")
print(h)

# Query the bot
elon_bot.query("How many companies does Elon Musk run?")
# Answer: Elon Musk runs four companies: Tesla, SpaceX, Neuralink, and The Boring Company
