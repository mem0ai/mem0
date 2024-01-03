from embedchain import App

app = App.from_config("config.yaml")
app.add("/path/to/your/folder", data_type="directory")

while True:
    user_input = input("Enter your question (type 'exit' to quit): ")

    # Break the loop if the user types 'exit'
    if user_input.lower() == "exit":
        break

    # Process the input and provide a response
    response = app.chat(user_input)
    print(response)
