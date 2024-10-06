from mem0.configs.base import MemoryConfig
from mem0.configs.history.my_sql import MysqlConfig
from mem0.configs.vector_stores.esvector import ESVectorConfig
from mem0.history.configs import HistoryDBConfig
from mem0.memory.main import Memory
from mem0.vector_stores.configs import VectorStoreConfig


config = MemoryConfig()

config.vector_store = VectorStoreConfig(
    provider="esvector",
    config=ESVectorConfig(
        # endpoint="https://ec74fdd3f31c4c50af17af6fb3ecef88.eastus2.azure.elastic-cloud.com:443",
        # api_key="YV9DajFZMEJhXzNna3RsWTVPMHE6QUdEb1gzVFJUai00TkxGRFVTeF9vZw==",    
        endpoint="http://localhost:9200",
    ).model_dump(),
)

config.history_db = HistoryDBConfig(
    provider="mysql",
    config=MysqlConfig(
        url="mysql+aiomysql://dfoadmin:F2RKGt75.&@digitalray-mysql-dev.mysql.database.azure.com:3306/digital_ray_dev"
    ).model_dump(),
)

m = Memory(config=config)

# m.reset()

result = m.add(
    "I like to play basketball on weekends.",
    user_id="mingrui",
    metadata={"category": "hobbies"},
)
print(f"{result}")

related_memory = m.search("help me plan my weekend", user_id="mingrui")
print(f"{related_memory}")

result = m.add(
    "I like to play badminton on weekends.",
    user_id="mingrui",
    metadata={"category": "hobbies"},
)
print(f"{result}")

related_memory = m.search("help me plan my weekend", user_id="mingrui")
print(f"{related_memory}")

result = m.add(
    "I don't like to play basketball on weekends.",
    user_id="mingrui",
    metadata={"category": "hobbies"},
)
print(f"{result}")

history = m.history("18edd901-4c81-4b28-9533-4ea5cb1379b3")
print(history)
