# Private AI

In this example, we will create a private AI using embedchain.

Private AI is useful when you want to chat with your data and you dont want to spend money and your data should stay on your machine.

## How to install

First create a virtual environment and install the requirements by running

```bash
pip install -r requirements.txt
```

## How to use

* Now open privateai.py file and change the line `app.add` to point to your directory or data source.
* If you want to add any other data type, you can browse the supported data types [here](https://docs.embedchain.ai/components/data-sources/overview)

* Now simply run the file by

```bash
python privateai.py
```

* Now you can enter and ask any questions from your data.