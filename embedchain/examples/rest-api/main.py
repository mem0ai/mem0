import logging
import os

import aiofiles
import yaml
from database import Base, SessionLocal, engine
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from models import DefaultResponse, DeployAppRequest, QueryApp, SourceApp
from services import get_app, get_apps, remove_app, save_app
from sqlalchemy.orm import Session
from utils import generate_error_message_for_api_keys

from embedchain import App
from embedchain.client import Client

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    title="Embedchain REST API",
    description="This is the REST API for Embedchain.",
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://github.com/embedchain/embedchain/blob/main/LICENSE",
    },
)


@app.get("/ping", tags=["Utility"])
def check_status():
    """
    Endpoint to check the status of the API
    """
    return {"ping": "pong"}


@app.get("/apps", tags=["Apps"])
async def get_all_apps(db: Session = Depends(get_db)):
    """
    Get all apps.
    """
    apps = get_apps(db)
    return {"results": apps}


@app.post("/create", tags=["Apps"], response_model=DefaultResponse)
async def create_app_using_default_config(app_id: str, config: UploadFile = None, db: Session = Depends(get_db)):
    """
    Create a new app using App ID.
    If you don't provide a config file, Embedchain will use the default config file\n
    which uses opensource GPT4ALL model.\n
    app_id: The ID of the app.\n
    config: The YAML config file to create an App.\n
    """
    try:
        if app_id is None:
            raise HTTPException(detail="App ID not provided.", status_code=400)

        if get_app(db, app_id) is not None:
            raise HTTPException(detail=f"App with id '{app_id}' already exists.", status_code=400)

        yaml_path = "default.yaml"
        if config is not None:
            contents = await config.read()
            try:
                yaml.safe_load(contents)
                # TODO: validate the config yaml file here
                yaml_path = f"configs/{app_id}.yaml"
                async with aiofiles.open(yaml_path, mode="w") as file_out:
                    await file_out.write(str(contents, "utf-8"))
            except yaml.YAMLError as exc:
                raise HTTPException(detail=f"Error parsing YAML: {exc}", status_code=400)

        save_app(db, app_id, yaml_path)

        return DefaultResponse(response=f"App created successfully. App ID: {app_id}")
    except Exception as e:
        logger.warning(str(e))
        raise HTTPException(detail=f"Error creating app: {str(e)}", status_code=400)


@app.get(
    "/{app_id}/data",
    tags=["Apps"],
)
async def get_datasources_associated_with_app_id(app_id: str, db: Session = Depends(get_db)):
    """
    Get all data sources for an app.\n
    app_id: The ID of the app. Use "default" for the default app.\n
    """
    try:
        if app_id is None:
            raise HTTPException(
                detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
                status_code=400,
            )

        db_app = get_app(db, app_id)

        if db_app is None:
            raise HTTPException(detail=f"App with id {app_id} does not exist, please create it first.", status_code=400)

        app = App.from_config(config_path=db_app.config)

        response = app.get_data_sources()
        return {"results": response}
    except ValueError as ve:
        logger.warning(str(ve))
        raise HTTPException(
            detail=generate_error_message_for_api_keys(ve),
            status_code=400,
        )
    except Exception as e:
        logger.warning(str(e))
        raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


@app.post(
    "/{app_id}/add",
    tags=["Apps"],
    response_model=DefaultResponse,
)
async def add_datasource_to_an_app(body: SourceApp, app_id: str, db: Session = Depends(get_db)):
    """
    Add a source to an existing app.\n
    app_id: The ID of the app. Use "default" for the default app.\n
    source: The source to add.\n
    data_type: The data type of the source. Remove it if you want Embedchain to detect it automatically.\n
    """
    try:
        if app_id is None:
            raise HTTPException(
                detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
                status_code=400,
            )

        db_app = get_app(db, app_id)

        if db_app is None:
            raise HTTPException(detail=f"App with id {app_id} does not exist, please create it first.", status_code=400)

        app = App.from_config(config_path=db_app.config)

        response = app.add(source=body.source, data_type=body.data_type)
        return DefaultResponse(response=response)
    except ValueError as ve:
        logger.warning(str(ve))
        raise HTTPException(
            detail=generate_error_message_for_api_keys(ve),
            status_code=400,
        )
    except Exception as e:
        logger.warning(str(e))
        raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


@app.post(
    "/{app_id}/query",
    tags=["Apps"],
    response_model=DefaultResponse,
)
async def query_an_app(body: QueryApp, app_id: str, db: Session = Depends(get_db)):
    """
    Query an existing app.\n
    app_id: The ID of the app. Use "default" for the default app.\n
    query: The query that you want to ask the App.\n
    """
    try:
        if app_id is None:
            raise HTTPException(
                detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
                status_code=400,
            )

        db_app = get_app(db, app_id)

        if db_app is None:
            raise HTTPException(detail=f"App with id {app_id} does not exist, please create it first.", status_code=400)

        app = App.from_config(config_path=db_app.config)

        response = app.query(body.query)
        return DefaultResponse(response=response)
    except ValueError as ve:
        logger.warning(str(ve))
        raise HTTPException(
            detail=generate_error_message_for_api_keys(ve),
            status_code=400,
        )
    except Exception as e:
        logger.warning(str(e))
        raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


# FIXME: The chat implementation of Embedchain needs to be modified to work with the REST API.
# @app.post(
#     "/{app_id}/chat",
#     tags=["Apps"],
#     response_model=DefaultResponse,
# )
# async def chat_with_an_app(body: MessageApp, app_id: str, db: Session = Depends(get_db)):
#     """
#     Query an existing app.\n
#     app_id: The ID of the app. Use "default" for the default app.\n
#     message: The message that you want to send to the App.\n
#     """
#     try:
#         if app_id is None:
#             raise HTTPException(
#                 detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
#                 status_code=400,
#             )

#         db_app = get_app(db, app_id)

#         if db_app is None:
#             raise HTTPException(
#               detail=f"App with id {app_id} does not exist, please create it first.",
#               status_code=400
#             )

#         app = App.from_config(config_path=db_app.config)

#         response = app.chat(body.message)
#         return DefaultResponse(response=response)
#     except ValueError as ve:
#             raise HTTPException(
#                 detail=generate_error_message_for_api_keys(ve),
#                 status_code=400,
#             )
#     except Exception as e:
#         raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


@app.post(
    "/{app_id}/deploy",
    tags=["Apps"],
    response_model=DefaultResponse,
)
async def deploy_app(body: DeployAppRequest, app_id: str, db: Session = Depends(get_db)):
    """
    Query an existing app.\n
    app_id: The ID of the app. Use "default" for the default app.\n
    api_key: The API key to use for deployment. If not provided,
    Embedchain will use the API key previously used (if any).\n
    """
    try:
        if app_id is None:
            raise HTTPException(
                detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
                status_code=400,
            )

        db_app = get_app(db, app_id)

        if db_app is None:
            raise HTTPException(detail=f"App with id {app_id} does not exist, please create it first.", status_code=400)

        app = App.from_config(config_path=db_app.config)

        api_key = body.api_key
        # this will save the api key in the embedchain.db
        Client(api_key=api_key)

        app.deploy()
        return DefaultResponse(response="App deployed successfully.")
    except ValueError as ve:
        logger.warning(str(ve))
        raise HTTPException(
            detail=generate_error_message_for_api_keys(ve),
            status_code=400,
        )
    except Exception as e:
        logger.warning(str(e))
        raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


@app.delete(
    "/{app_id}/delete",
    tags=["Apps"],
    response_model=DefaultResponse,
)
async def delete_app(app_id: str, db: Session = Depends(get_db)):
    """
    Delete an existing app.\n
    app_id: The ID of the app to be deleted.
    """
    try:
        if app_id is None:
            raise HTTPException(
                detail="App ID not provided. If you want to use the default app, use 'default' as the app_id.",
                status_code=400,
            )

        db_app = get_app(db, app_id)

        if db_app is None:
            raise HTTPException(detail=f"App with id {app_id} does not exist, please create it first.", status_code=400)

        app = App.from_config(config_path=db_app.config)

        # reset app.db
        app.db.reset()

        remove_app(db, app_id)
        return DefaultResponse(response=f"App with id {app_id} deleted successfully.")
    except Exception as e:
        raise HTTPException(detail=f"Error occurred: {str(e)}", status_code=400)


if __name__ == "__main__":
    import uvicorn

    is_dev = os.getenv("DEVELOPMENT", "False")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=bool(is_dev))
